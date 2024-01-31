import sys
from copy import deepcopy
from traceback import print_exception
from typing import Optional, Union

import disnake
from disnake.channel import TextChannel, VoiceChannel
from disnake.ext import commands
from disnake.ext.commands.context import Context
from disnake.member import Member
from disnake.user import User
from disnake.utils import find

from constants import DECKLIST_FILE, MAX_AUX_HAND_SIZE
from errors import CardMissingBuybackError, CardMissingFlashbackError, CardNotFoundError, ImageNotFoundError
from lib.card_image import get_image_file_location, get_card_images
from lib.deck import Deck
from lib.discord import message_is_in_game_channel, message_is_in_server
from lib.formatting import format_card_list
from lib.game_state import load_game_state, save_game_state
from lib.messages import send_game_channel_warning_message
from models import MemberInfo, OneWithDeathGame


with open("api_key.txt", "r") as f:
    TOKEN = f.read()


# TODO: refactor this into separate modules for different commands
    
# TODO: figure out how to reduce game finding/checking boilerplate


# TODO: refactor this into a singleton or something -- in-memory data layer? SQLite?
RUNNING_GAMES: list[OneWithDeathGame] = []

intents = disnake.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def find_game_by_member_id(member_id: str) -> Optional[OneWithDeathGame]:
    return find(lambda g: find(lambda m: m.id == member_id, g.members), RUNNING_GAMES)


@bot.command()
async def startgame(ctx: Context, *member_names_for_game):
    if not message_is_in_server(ctx):
        await ctx.send(f"You can only start the game from within the server where you want to play it")
        return

    print(f"Starting new game for member {ctx.author.mention}")
    game_members: list[Member] = [ctx.author]

    # find game members
    for member_name in member_names_for_game:
        members = await ctx.guild.search_members(member_name)

        if not any(members):
            await ctx.send(
                f'ERROR: Could not find member {member_name} in the server. Was there a typo, or were quotes (") forgotten around a name with spaces?'
            )
            return

        game_members.append(members[0])

    # TODO: stop people from starting game if member is already in a game

    # create relevant channels
    overwrites = {
        ctx.guild.default_role: disnake.PermissionOverwrite(view_channel=False),
        ctx.guild.me: disnake.PermissionOverwrite(view_channel=True),
        **{
            member: disnake.PermissionOverwrite(view_channel=True)
            for member in game_members
        },
    }

    admin_role = ctx.guild.get_role(0)
    if admin_role:
        overwrites[admin_role] = disnake.PermissionOverwrite(view_channel=True)

    text_channel_name = f"{ctx.author}-one-with-death"
    print(f"Creating text channel {text_channel_name}")
    text_channel: TextChannel = await ctx.guild.create_text_channel(
        text_channel_name, overwrites=overwrites
    )

    voice_channel_name = f"{ctx.author}-one-with-death-vc"
    print(f"Creating voice channel {voice_channel_name}")
    voice_channel: VoiceChannel = await ctx.guild.create_voice_channel(
        voice_channel_name, overwrites=overwrites
    )

    await ctx.send(
        f"New channels have been created for a One with Death game hosted by {ctx.author.mention}, including the players {', '.join([member.mention for member in game_members[:-1]])} and {game_members[-1].mention}"
    )

    # initialize and save game state
    game_state = OneWithDeathGame(
        id=f"owd-{ctx.author}",
        members=[
            MemberInfo(id=member.id, name=member.name, mention=member.mention)
            for member in game_members
        ],
        deck=Deck.from_file(decklist_file=DECKLIST_FILE, member_ids=[member.id for member in game_members]),
        text_channel=text_channel.id,
        voice_channel=voice_channel.id
    )

    RUNNING_GAMES.append(game_state)
    save_game_state(RUNNING_GAMES)

    # send welcome messages
    for member in game_members:
        # TODO: iron out what this specifically should say w/john and danny
        # TODO: include nix image as attachment on this message
        # TODO: include rules description here, or a link to it
        content=f"""Welcome to One with Death!

I'll be letting you know in this chat what cards you draw. Any non-private commands should be sent in {text_channel.mention} in {ctx.guild.name}, though!

The main important commands are:
`!rules` - Show the rules of One with Death.

`!draw [num_cards=1]` - Draw cards from the Deck of Death. If no number of cards is provided, one card is drawn by default. 

`!play card_name` - Play a card which you've previously drawn from the Deck of Death

`!scry num_cards` - Scry the given number of cards. This command must be followed up with the !reorder command in order to submit the new card order for your scryed cards.

`!reorder 1 2 3` - Re-order the cards from a recently run scry. The card numbers should be separated by a space.

`!help` - See a full list of available commands, or get more detailed help for a command (e.g. !help scry)

You start with a Nix card automatically!"""
        await member.send(content, file=disnake.File(get_image_file_location("Nix")))


@bot.command()
async def endgame(ctx: Context, game_id: Optional[str]=None):
    """
    End the game you are currently in, deleting the game state and channels
    """
    # TODO: allow admins to manually specify game id, but only admins
    if not game_id:
        game = find_game_by_member_id(ctx.author.id)
        if not game:
            await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
            return
        else:
            game_id = game.id

    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    game_index_list = [i for i, g in enumerate(RUNNING_GAMES) if g.id == game_id]

    if not game_index_list:
        await ctx.send(f"Game with id {game_id} was not found")
    else:
        game_index = game_index_list[0]
        game = RUNNING_GAMES[0]
        del RUNNING_GAMES[game_index]
        save_game_state(RUNNING_GAMES)

        await ctx.guild.get_channel(game.text_channel).delete()
        await ctx.guild.get_channel(game.voice_channel).delete()
        
        for member in game.members:
            await ctx.guild.get_member(member.id).send(f"The game {game.id} has ended!")


async def handle_draw(ctx: Context, game: OneWithDeathGame, member: Union[User, Member], num_cards: int):
    drawn_cards = game.deck.draw(member_id=member.id, num_cards=num_cards)
    save_game_state(RUNNING_GAMES)
    
    # TODO: include card picture as attachment once I get them from danny
    drawn_cards_display = format_card_list(drawn_cards)
    content = f"You drew {'these' if num_cards > 1 else 'this'} {num_cards} card{'s' if num_cards > 1 else ''}: {drawn_cards_display}"
    failed_to_load_images = False

    card_images = []
    try:
        card_images = [disnake.File(get_image_file_location(card_name)) for card_name in drawn_cards]
    except Exception as e:
        print(f"Failed to load card images for card list: {drawn_cards}")
        print_exception(
            type(e), e, e.__traceback__, file=sys.stderr
        )
        failed_to_load_images = True
        # intentionally eat the error so we still at least send the drawn cards

    await member.send(content, files=card_images)
    if failed_to_load_images:
        await member.send("Sorry, I had some trouble loading the images for this draw.")

    game_channel = ctx.guild.get_channel(game.text_channel)
    if game_channel != ctx.channel:
        await game_channel.send(f"{member.mention} drew {num_cards} cards")

    drawn_owds = [True for c in drawn_cards if c == 'One with Death']
    if any(drawn_owds):
        card_image = disnake.File(get_image_file_location("One with Death"))
        await game_channel.send(f"{member.mention} drew {len(drawn_owds)} One with Death card{'s' if len(drawn_owds) > 1 else ''}!", file=card_image)
        await member.send(f"You got {'{}'.format(len(drawn_owds)) if len(drawn_owds) > 1 else 'a'} Charon's Obol{'s' if len(drawn_owds) > 1 else ''}!", file=disnake.File(get_image_file_location("Charon's Obol"))) 

    hand = game.deck.get_hand(member.id)
    if len(hand) > MAX_AUX_HAND_SIZE:
        await member.send(f"Your hand size of {len(hand)} is over the limit of {MAX_AUX_HAND_SIZE} cards!")


@bot.command()
async def draw(ctx: Context, num_cards: str="1"):
    """
    Draw cards from the Deck of Death.

    Cards drawn will be DM'd to you with images of the cards included.

    If a One with Death is drawn, it is automatically put into the resolution stack and the fact it was drawn is sent to the game channel.
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    
    if not message_is_in_game_channel():
        await send_game_channel_warning_message(ctx, game)
        return

    try:
        num_cards = int(num_cards)
    except:
        await ctx.send(f"Received invalid non-number argument for draw: {num_cards}")
        return

    await handle_draw(ctx, game, ctx.author, num_cards)


@bot.command()
async def drawall(ctx: Context, num_cards: str="1"):
    """
    Draw cards from the Deck of Death for all players.

    Cards drawn will be DM'd to each player with images of the cards included.

    If a One with Death is drawn, it is automatically put into the resolution stack and the fact it was drawn is sent to the game channel.
    """ 
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    
    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    try:
        num_cards = int(num_cards)
    except:
        await ctx.send(f"Received invalid non-number argument for draw: {num_cards}")
        return
    
    for member in game.members:
        await handle_draw(ctx, game, ctx.guild.get_member(member.id), num_cards)


@bot.command()
async def drawother(ctx: Context, num_cards: str="1"):
    """
    Draw cards from the Deck of Death for all players except the command submitter.

    Cards drawn will be DM'd to each player with images of the cards included.

    If a One with Death is drawn, it is automatically put into the resolution stack and the fact it was drawn is sent to the game channel.
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    
    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return
    
    try:
        num_cards = int(num_cards)
    except:
        await ctx.send(f"Received invalid non-number argument for draw: {num_cards}")
        return
    
    for member in game.members:
        if member.id == ctx.author.id:
            # don't draw for the person submitting the command
            continue
        await handle_draw(ctx, game, ctx.guild.get_member(member.id), num_cards)


@bot.command()
async def redrawexile(ctx: Context):
    """
    Exile your entire hand, then re-draw it
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    
    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    # discard hand, toss the discarded cards into the exile list, then re-draw
    exiled_hand = game.deck.discard_hand(ctx.author.id)
    num_cards = len(exiled_hand)
    
    game.exile.extend(exiled_hand)
    
    await handle_draw(ctx, game, num_cards)
    save_game_state(RUNNING_GAMES)

    await ctx.send(f"{ctx.author.mention} exiled and re-drew {num_cards} cards")


@bot.command()
async def redrawall(ctx: Context):
    """
    Put all players hands back into the library, then re-draw them to their original sizes
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    member_num_cards: dict[int, int] = {}

    for member in game.members:
        discarded_cards = game.deck.discard_hand(member.id)
        game.deck.add_to_deck(*discarded_cards)
        member_num_cards[member.id] = len(discarded_cards)

    game.deck.shuffle()
    
    for member in game.members:
        await handle_draw(ctx, game, ctx.guild.get_member(member.id), member_num_cards[member.id])
    
    game_channel = ctx.guild.get_channel(game.text_channel)
    await game_channel.send(f"{ctx.author.mention} triggered a re-draw for all players")


async def peek_for_reorder(ctx: Context, num_cards: str, follow_up_action: Optional[str]=None, action_word="peek"):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    
    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return
    
    if game.waiting_for_response_from:
        await ctx.send(f"Currently waiting to resolve an action ({game.waiting_for_response_action}) from {game.waiting_for_response_from.name}, so no other actions can be taken")
        return

    try:
        num_cards = int(num_cards)
    except:
        await ctx.send(f"Received invalid non-number argument for draw: {num_cards}")
        return

    print(f"Scrying {num_cards} cards for {ctx.author} in game {game.id}")
    peeked_cards = game.deck.peek(num_cards)
    
    # TODO: where do I get card pictures from?
    numbered_cards = [f"`{i + 1}. {peeked_cards[i]}`" for i in range(len(peeked_cards))]
    cards_display = '\n'.join(numbered_cards)

    card_images = []
    for card in peeked_cards:
        try:
            card_image = disnake.File(get_image_file_location(card))
            card_images.append(card_image)
        except ImageNotFoundError:
            print(f"Error retrieving image for {card}")

    content = f"You {action_word}ed these {num_cards} cards:\n{cards_display}\n"
    await ctx.author.send(content, files=card_images)

    input_directions = 'Respond to me with a `!reorder` command with the re-ordered card numbers, separated by spaces'
    if follow_up_action == "reorder:scry":
        input_directions = ", grouped by top/bottom as a prefixing word.\n\nFor example, for a `!scry 3` you might write: `!reorder top 1 2 bottom 3`."
    elif follow_up_action == "reorder:rearrange":
        input_directions = ".\n\nFor example, for a `!rearrange 3` you might write: `!reorder 3 1 2`."

    if follow_up_action:
        await ctx.author.send(f"{input_directions}")
        game.waiting_for_response_from = MemberInfo(ctx.author.id, ctx.author.display_name, ctx.author.mention)
        game.waiting_for_response_action = follow_up_action
        game.waiting_for_response_number = num_cards

        save_game_state(RUNNING_GAMES)

    # if this was run outside the game channel, notify the game channel it happened
    game_channel = ctx.guild.get_channel(game.text_channel)
    
    if game_channel != ctx.channel:
        await game_channel.send(f"{ctx.author.mention} peeked at {num_cards} cards")


@bot.command()
async def scry(ctx: Context, num_cards: str):
    """
    Peek at the top cards of the Deck of Death, then gain the ability to re-arrange those cards as desired on the top and bottom of the deck.

    Must be followed by a !reorder command to re-order the scried cards.
    A !reorder for a scry is in the format: !reorder top 1 2 bottom 3
    In which the numbers align from top->bottom for the card numbers specified in the message from the bot.
    """
    await peek_for_reorder(ctx, num_cards, "reorder:scry")


@bot.command()
async def rearrange(ctx: Context, num_cards: str):
    """
    Peek at the top cards of the Deck of Death, then gain the ability to re-arrange those cards as desired on the top and bottom of the deck.

    Must be followed by a !reorder command to re-order the scried cards.
    A !reorder for a rearrange is in the format: !reorder 3 1 2 
    In which the numbers align from top->bottom for the card numbers specified in the message from the bot.
    """
    await peek_for_reorder(ctx, num_cards, "reorder:rearrange")


@bot.command()
async def peek(ctx: Context, num_cards: str):
    """
    Peek at the top cards of the deck. The cards you see will be sent to you in a DM.
    """
    await peek_for_reorder(ctx, num_cards)


@bot.command()
async def reorder(ctx: Context, *new_card_indexes):
    """
    Can only be used after a scry command was just run by the same player.
    Give the command the cards you're re-ordering in the order that you want them, separated by semicolons (;).
    If no argument is given, the re-order will resolve without changing the card order.

    Examples:
    
    For a scry                     -> !reorder top 1 2 bottom 3
    For a scry where all go on top -> !reorder top 1 2
    For a rearrange                -> !reorder 1 2 3
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if game.waiting_for_response_from.id and game.waiting_for_response_from.id != ctx.author.id:
        await ctx.send(f"I'm currently waiting to resolve an action ({game.waiting_for_response_action}) from player {game.waiting_for_response_from}, so no other actions can be taken")
        return

    if game.waiting_for_response_action not in ["reorder:scry", "reorder:rearrange"]:
        await ctx.send(f"I'm currently waiting to resolve a non-reorder action {game.waiting_for_response_action} from you, so a re-order is not valid")
        return

    non_specifier_inputs = [i for i in new_card_indexes if i.lower() != "top" and i.lower() != "bottom"]
    if game.waiting_for_response_number != len(non_specifier_inputs):
        await ctx.send(f"I expected to be re-ordering {game.waiting_for_response_number} cards, but instead I got {len(new_card_indexes)} ({new_card_indexes}).")

    # At this point, we know it's the right player making a valid action type
    converted_new_card_indexes = []
    for item in new_card_indexes:
        if item.lower() == 'top' or item.lower() == 'bottom':
            converted_new_card_indexes.append(item.lower())
        else:
            try:
                index = int(item)
                converted_new_card_indexes.append(index)
            except:
                await ctx.send(f"It looks like I got an invalid argument: {item}. Only numbers and the words 'top' and 'bottom' are valid arguments for re-ordering.")
                return


    indexes_only = [i for i in converted_new_card_indexes if isinstance(i, int)]

    expected_indexes = [i + 1 for i in range(len(indexes_only))]
    if sorted(indexes_only) != expected_indexes:
        await ctx.send(f"Invalid card indexes for rearrange re-ordering provided: {[i for i in indexes_only if i not in expected_indexes]}")
        return

    if game.waiting_for_response_action == "reorder:scry":
        new_top_cards, new_bottom_cards = [], []
        top_specifier_index = converted_new_card_indexes.index("top") if "top" in converted_new_card_indexes else -1
        bottom_specifier_index = converted_new_card_indexes.index("bottom") if "bottom" in converted_new_card_indexes else -1

        if top_specifier_index >= 0 and bottom_specifier_index >= 0:
            # bottom and top both present, figure out which indexes go to which side
            if top_specifier_index > bottom_specifier_index:
                new_top_cards = indexes_only[top_specifier_index - 1:]
                new_bottom_cards = indexes_only[:top_specifier_index - 1]
            else:
                new_top_cards = indexes_only[:bottom_specifier_index - 1]
                new_bottom_cards = indexes_only[bottom_specifier_index - 1:]
        elif top_specifier_index < 0 and bottom_specifier_index >= 0:
            # only bottom
            new_top_cards = []
            new_bottom_cards = indexes_only
        else:
            # top only
            # this is top only regardless of whether we have a top specifier
            # because w/no specifier the default is also top only
            new_top_cards = indexes_only
            new_bottom_cards = []

        game.deck.reorder_scry(new_top_cards, new_bottom_cards)
    elif game.waiting_for_response_action == "reorder:rearrange":
        game.deck.reorder_rearrange(indexes_only)
    else:
        await ctx.send(f"Uh-oh, I don't know how to deal with the action {game.waiting_for_response_action}. Reach out to @snowydark to get this fixed, because it shouldn't happen.")
    
    await ctx.send("Cards successfully re-ordered")
    game.waiting_for_response_action = None
    game.waiting_for_response_from = None
    game.waiting_for_response_number = None
    save_game_state(RUNNING_GAMES)


@bot.command()
async def play(ctx: Context, *card_words):
    """
    Play a card, sending it to the graveyard.

    Only cards drawn from the Deck of Death can be played this way.

    To buy back a card, use the !buyback command after !play-ing it
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    card_name = ' '.join(card_words)

    actual_card_name = ''
    try:
        actual_card_name = game.deck.play(card_name, member_id=ctx.author.id)
    except ValueError as e:
        await ctx.send(e)
        return
    
    print(f"Playing {actual_card_name} in game {game.id}")
    game.graveyard.insert(actual_card_name)
    save_game_state(RUNNING_GAMES)

    # notify the game channel this happened
    card_image = None
    try:
        card_image = disnake.File(get_image_file_location(actual_card_name))
    except ImageNotFoundError:
        print(f"Error retrieving image for {actual_card_name}")

    game_channel = ctx.guild.get_channel(game.text_channel)
    await game_channel.send(f"{ctx.author.mention} played {actual_card_name}", file=card_image)


@bot.command()
async def discard(ctx: Context, *card_words):
    """
    Discard a specific from your hand into the graveyard
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    card_name = ' '.join(card_words)

    actual_card_name = ''
    try:
        actual_card_name = game.deck.discard(card_name, member_id=ctx.author.id)
    except ValueError as e:
        await ctx.send(e)
        return
    
    print(f"Discarding {actual_card_name} in game {game.id}")
    game.graveyard.insert(actual_card_name)
    save_game_state(RUNNING_GAMES)

    # notify the game channel this happened
    card_image = None
    try:
        card_image = disnake.File(get_image_file_location(actual_card_name))
    except ImageNotFoundError:
        print(f"Error retrieving image for {actual_card_name}")

    game_channel = ctx.guild.get_channel(game.text_channel)
    await game_channel.send(f"{ctx.author.mention} discarded {actual_card_name}", file=card_image)


@bot.command()
async def discardall(ctx: Context):
    """
    Discard all cards from your hand into the graveyard
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    print(f"Discarding hand of {ctx.author.mention} in game {game.id}")    
    discarded_cards = []
    hand = deepcopy(game.deck.get_hand(ctx.author.id))
    print(f"Hand: {hand}")
    for card_name in hand:
        actual_card_name = game.deck.discard(card_name, member_id=ctx.author.id)
        game.graveyard.insert(actual_card_name)
        discarded_cards.append(card_name)

    save_game_state(RUNNING_GAMES)

    # notify the game channel this happened
    game_channel = ctx.guild.get_channel(game.text_channel)
    await game_channel.send(f"{ctx.author.mention} discarded {', '.join(discarded_cards)}")


@bot.command()
async def buyback(ctx: Context, *card_words):
    """
    Buy back a card, keeping it from the graveyard and leaving it playable.
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    
    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    card_name = ' '.join(card_words)
    
    if not game.deck.is_buyback_valid(card_name):
        await ctx.send(f"You can't buy back a card that wasn't the card most recently played from the Deck of Death. \n\nThe most recently played card is: {game.deck._last_card_played}")
        return

    try:
        actual_card = game.graveyard.buyback(card_name)
        game.deck.buyback(card=actual_card, member_id=ctx.author.id)
    except CardNotFoundError:
        await ctx.send(f"The card {card_name} was not found in the graveyard")
        return
    except CardMissingBuybackError:
        await ctx.send(f"The card {card_name} does not have buyback")
        return

    save_game_state(RUNNING_GAMES)
    game_channel = ctx.guild.get_channel(game.text_channel)
    await game_channel.send(f"{ctx.author.mention} bought back {actual_card}")


@bot.command()
async def flashback(ctx: Context, *card_words):
    """
    Play a card from the graveyard via Flashback

    Will only work if the card in question is both in the graveyard and has flashback
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if not message_is_in_game_channel(ctx, game):
        await send_game_channel_warning_message(ctx, game)
        return

    card_name = ' '.join(card_words)

    try:
        actual_card_name = game.graveyard.flashback(card_name)
    except CardNotFoundError:
        await ctx.send(f"The card {card_name} was not found in the graveyard")
        return
    except CardMissingFlashbackError:
        await ctx.send(f"The card {card_name} does not have flashback")
        return

    game.exile.append(actual_card_name)
    save_game_state(RUNNING_GAMES)

    game_channel = ctx.guild.get_channel(game.text_channel)

    card_image = None
    try:
        card_image = disnake.File(get_image_file_location(actual_card_name))
    except ImageNotFoundError:
        print(f"Error retrieving image for {actual_card_name}")

    await game_channel.send(f"{actual_card_name} has been flashbacked by {ctx.author.mention} and is now exiled", file=card_image)


@bot.command()
async def mill(ctx: Context, num_cards: str):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    try:
        num_cards_int = int(num_cards)
    except:
        await ctx.send(f"Received invalid non-number argument for draw: {num_cards}")
        return

    milled_cards, was_owd_milled = game.deck.mill(num_cards_int)
    game.graveyard.cards.extend(milled_cards)

    card_images = get_card_images(milled_cards)

    save_game_state(RUNNING_GAMES)
    
    game_channel = ctx.guild.get_channel(game.text_channel)
    if was_owd_milled:
        await game_channel.send(f"{ctx.author.mention} milled {num_cards} cards, including a One with Death! The deck was shuffled because the One with Deaths were shuffled back in after being milled.", files=card_images)
    else:
        await game_channel.send(f"{ctx.author.mention} milled {num_cards} cards", files=card_images)


def escape(ctx: Context, *card_words):
    pass


@bot.command()
async def shuffle(ctx: Context):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return


    game.deck.shuffle()
    save_game_state(RUNNING_GAMES)

    game_channel = ctx.guild.get_channel(game.text_channel)
    await game_channel.send(f"{ctx.author.mention} shuffled the Deck of Death.")


@bot.command()
async def resolve(ctx: Context, *card_words):
    """
    Resolve a card from the game's resolution stack (e.g. One with Death)

    The resolved card gets sent to the graveyard
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if not card_words:
        await ctx.send(f"You must provide either a number of cards to resolve from the stack, or the name of the card to resolve, or a card name then a number of cards to resolve")
        return

    # if the last word is a number, take that as the num of copies to resolve 
    num_cards_to_resolve = 1
    if card_words[-1].isdigit():
        num_cards_to_resolve = int(card_words[-1])
        card_words = card_words[:-1]

    card_name = ' '.join(card_words)

    resolved_cards = []
    for _ in range(num_cards_to_resolve):
        actual_card_name = ''
        try:
            actual_card_name = game.deck.resolve(card_name)
            resolved_cards.append(actual_card_name)
        except ValueError:
            await ctx.send(f"{card_name} is not in the resolution stack")
            break

        if actual_card_name != "One with Death":
            game.graveyard.insert(actual_card_name)

    if resolved_cards:
        save_game_state(RUNNING_GAMES)
        
        game_channel = ctx.guild.get_channel(game.text_channel)
        await game_channel.send(f"Resolved {'a' if len(resolved_cards) == 1 else str(num_cards_to_resolve)} card{'s' if len(resolved_cards) > 1 else ''}: {format_card_list(resolved_cards)} The resolution stack is now {':' + format_card_list(game.deck._waiting_to_resolve) if game.deck._waiting_to_resolve else 'empty'}")


@bot.command()
async def stack(ctx: Context, *card_words):
    """
    View the current resolution stack
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    save_game_state(RUNNING_GAMES)
    
    game_channel = ctx.guild.get_channel(game.text_channel)
    if game.deck._waiting_to_resolve:
        card_images = get_card_images(game.deck._waiting_to_resolve)
        await game_channel.send(f"The resolution stack is: {format_card_list(game.deck._waiting_to_resolve)}", files=card_images)
    else:
        await game_channel.send(f"The resolution stack is empty!")    

@bot.command()
async def resolvetop(ctx: Context, *card_words):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    card_name = ' '.join(card_words)

    try:
        actual_card_name = game.deck.resolve(card_name, resolve_to_top=True)
    except ValueError:
        await ctx.send(f"{card_name} is not in the resolution stack")
    
    save_game_state(RUNNING_GAMES)
    
    game_channel = ctx.guild.get_channel(game.text_channel)
    await game_channel.send(f"Resolved a copy of {actual_card_name}. The resolution stack is now: {game.deck._waiting_to_resolve}")


@bot.command()
async def pullfromgrave(ctx: Context, *card_words):
    """
    Pull a specific card out of the graveyard into your hand

    Examples:
    !pullfromgrave angels grace
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    card_name = ' '.join(card_words)
    actual_card_name = game.graveyard.pull_card_by_name(card_name)
    game.deck.add_card_to_hand(ctx.author.id, actual_card_name)
    save_game_state(RUNNING_GAMES)

    
    game_channel = ctx.guild.get_channel(game.text_channel)
    await game_channel.send(f"{ctx.author.mention} pulled {actual_card_name} from the grave")


@bot.command()
async def exilegrave(ctx: Context, *card_indexes):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    card_index_list = [int(card_index) for card_index in card_indexes]

    out_of_bounds_indexes = [i for i in card_index_list if i > len(game.graveyard) or i < 1]
    if any(out_of_bounds_indexes):
        await ctx.send(f"That `!exilegrave` command was invalid, because some indexes were out of bounds. An index for the graveyard should be no less than 1 and no more than the size of the graveyard ({len(graveyard)}). The offending indexes were: {', '.join(out_of_bounds_indexes)}")
        return

    cards_exiled = []

    for card_index in card_index_list:
        card_name = game.graveyard.pull_card_by_index(card_index - 1)
        game.exile.append(card_name)
        cards_exiled.append(card_name)

    game_channel = ctx.guild.get_channel(game.text_channel)
    cards_str = '\n'.join(cards_exiled)
    await game_channel.send(f"{ctx.author.mention} exiled these cards from the graveyard:\n```\n{cards_str}\n```")


@bot.command()
async def hand(ctx: Context, show_to: str=None):
    """
    Get a view of your current Deck of Death hand, or show it to someone else.

    If no argument is provided, the hand is sent in a DM to you. If you want to show someone else, give their name as an argument.
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    
    recipient = ctx.author
    if show_to:
        if not message_is_in_game_channel(ctx, game):
            await ctx.send(f"To show someone else your hand, you must post the `!hand <member>` command from the channel of the game")
            return
        enriched_members = [ctx.guild.get_member(m.id) for m in game.members]
        found_members = [m for m in enriched_members if m.name.lower() == show_to.lower() or m.display_name.lower() == show_to.lower()]
        if not found_members:
            await ctx.send(f"I couldn't find {show_to} to show the hand to")
            return
        else:
            recipient = found_members[0]

    hand = game.deck.get_hand(member_id=ctx.author.id)
    if hand:
        card_images = get_card_images(hand)        

        if recipient.id == ctx.author.id:
            await recipient.send(f"The cards in your hand are:\n{format_card_list(hand)}", files=card_images)
        else:
            await recipient.send(f"The cards in {ctx.author.display_name}'s hand are:\n{format_card_list(hand)}", files=card_images)
    else:
        if recipient.id == ctx.author.id:
            await recipient.send(f"Your hand is empty!")
        else:
            await recipient.send(f"{ctx.author.display_name}'s hand is empty!")


@bot.command()
async def graveyard(ctx: Context):
    """
    Get a list of cards currently in the graveyard for the Deck of Death
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if game.graveyard.cards:
        content = "The graveyard for the Deck of Death has these cards:\n"
        # TODO: make a util function for this card formatting stuff
        content += "```\n"
        content += "\n".join(game.graveyard.cards)
        content += "\n```"
        await ctx.send(content)
    else:
        await ctx.send("The graveyard for the Deck of Death is empty")


@bot.command()
async def exile(ctx: Context):
    """
    Get a list of cards exiled from the Deck of Death
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return

    if game.exile:
        content = "The exile pile for the Deck of Death has these cards:\n"
        content += "```\n"
        content += "\n".join(game.exile)
        content += "\n```"
        await ctx.send(content)
    else:
        await ctx.send("The exile pile for the Deck of Death is empty")


@bot.command()
async def recur(ctx: Context):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    
    recurrable_cards = game.graveyard.get_recurrable_cards()

    if recurrable_cards:
        content = "The recurrable cards in the communal graveyard are:\n"
        content += "```\n"
        content += "\n".join(recurrable_cards)
        content += "\n```"
        await ctx.send(content)
    else:
        await ctx.send("There are no recurrable cards in the graveyard")
        

@bot.command()
async def decksize(ctx: Context):
    """
    Get the current size of the Deck of Death

    Examples:
    !decksize
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.mention} is currently playing in")
        return
    ctx.send(f"The Deck of Death has {len(game.deck.cards)} cards left")


@bot.command()
async def card(ctx: Context, *card_words):
    card_image: disnake.File = None
    try:
        card_name = ' '.join(card_words)
        card_image = disnake.File(get_image_file_location(card_name))
    except ImageNotFoundError:
        await ctx.send(f"Sorry, I couldn't find an image for {card_name}")
        return
    except Exception as e:
        await ctx.send(f"Sorry, I ran into an unexpected error while loading the image for {card_name}")
        return

    await ctx.send(file=card_image)


@bot.command()
async def rules(ctx: Context):
    """
    Get the rules for One with Death

    Examples:
    !rules
    """
    await ctx.send("These still need to be defined :)")





@bot.event
async def on_command_error(ctx: Context, e: commands.errors.CommandError):
    print_exception(
        type(e), e, e.__traceback__, file=sys.stderr
    )
    print(f"Author: {ctx.author.name}, Command: {ctx.command}, Error: {e}")

    if isinstance(e, commands.errors.MissingRequiredArgument):
        await ctx.send(f"Looks like there are missing arguments from that command. You can use `!help {{command}}` to get instructions and examples of how to use a command.\n\nThe error I got for this was: `{e}`")


def main():
    global RUNNING_GAMES
    RUNNING_GAMES = load_game_state()

    print("Running bot...")
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
