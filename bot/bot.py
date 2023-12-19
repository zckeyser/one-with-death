from dataclasses import dataclass
import json
import os
import traceback
from typing import Optional

import disnake
from disnake.channel import TextChannel, VoiceChannel
from disnake.ext import commands
from disnake.ext.commands.context import Context
from disnake.member import Member
from disnake.utils import find


from constants import DECKLIST_FILE, LIST_DELIMITER
from lib.deck import Deck
from lib.graveyard import Graveyard
from lib.game_state import load_game_state, save_game_state
from models import MemberInfo, OneWithDeathGame

with open("api_key.txt", "r") as f:
    TOKEN = f.read()


# TODO: refactor this into a singleton or something -- in-memory data layer? SQLite?
RUNNING_GAMES: list[OneWithDeathGame] = []

intents = disnake.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def find_game_by_member_id(member_id: str) -> Optional[OneWithDeathGame]:
    return find(lambda g: find(lambda m: m.id == member_id, g.members), RUNNING_GAMES)


@bot.command()
async def startgame(ctx: Context, *member_names_for_game: list[str]):
    if not ctx.guild:
        await ctx.send(f"You can only start the game from within the server where you want to play it")
        return

    print(f"Starting new game for member {ctx.author.display_name}")
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
        f"New channels have been created for a One with Death game hosted by {ctx.author.display_name}, including the players {', '.join([member.display_name for member in game_members[:-1]])} and {game_members[-1].name}"
    )

    # initialize and save game state
    game_state = OneWithDeathGame(
        id=f"owd-{ctx.author}",
        members=[
            MemberInfo(id=member.id, name=member.name, mention=member.mention)
            for member in game_members
        ],
        deck=Deck.from_file(DECKLIST_FILE, f"owd-{ctx.author.display_name}-library"),
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

`!reorder card1;card2;card3` - Re-order the cards from a recently run scry. The card names should be separated by semicolons.

`!help` - See a full list of available commands, or get more detailed help for a command (e.g. !help scry)

You start with a Nix card automatically!"""
        await member.send(content)


@bot.command()
async def endgame(ctx: Context, game_id: Optional[str]=None):
    """
    End the game you are currently in, deleting the game state and channels
    """

    if not ctx.guild:
        await ctx.send(f"You can only end the game from the server where you're playing the game")

    # TODO: allow admins to manually specify game id, but only admins
    if not game_id:
        game_id = find_game_by_member_id(ctx.author.id).id
        if not game_id:
            # TODO: better error message
            await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")

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


@bot.command()
async def draw(ctx: Context, num_cards_str: str="1"):
    """
    Draw cards from the Deck of Death.

    Cards drawn will be DM'd to you with images of the cards included.

    If a One with Death is drawn, it is automatically put into the resolution stack and the fact it was drawn is sent to the game channel.
    """
    if not ctx.guild:
        await ctx.send(f"You can only send game-changing commands (draw, scry, flashback, buyback, play) in the server where you're playing the game")
        return
    
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")
        return
    
    try:
        num_cards = int(num_cards_str)
    except:
        await ctx.send(f"Received invalid non-number argument for draw: {num_cards_str}")
        return

    drawn_cards = game.deck.draw(member_id=ctx.author.id, num_cards=num_cards)
    save_game_state(RUNNING_GAMES)
    
    # TODO: include card picture as attachment once I get them from danny
    content = f"You drew {'these' if num_cards > 1 else 'this'} {num_cards} card{'s' if num_cards > 1 else ''}: {', '.join(drawn_cards)}"
    await ctx.author.send(content)

    game_channel = ctx.guild.get_channel(game.text_channel)
    if game_channel != ctx.channel:
        await game_channel.send(f"{ctx.author} drew {num_cards} cards")

    if any([True for c in drawn_cards if c == 'One with Death']):
        # TODO: Include OWD image here?
        await game_channel.send(f"{ctx.author.mention} drew One with Death!")


@bot.command()
async def scry(ctx: Context, num_cards_str: str=1):
    """
    Peek at the top cards of the Deck of Death

    Must be followed by a !reorder command to re-order the scried cards.
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.ndisplay_nameame} is currently playing in")
        return
    
    if game.waiting_for_response_from:
        await ctx.send(f"Currently waiting to resolve an action ({game.waiting_for_response_action}) from player {game.waiting_for_response_from}, so no other actions can be taken")
        return

    try:
        num_cards = int(num_cards_str)
    except:
        await ctx.send(f"Received invalid non-number argument for draw: {num_cards_str}")
        return

    print(f"Scrying {num_cards} cards for {ctx.author} in game {game.id}")
    scryed_cards = game.deck.peek(num_cards)
    
    # TODO: where do I get card pictures from?
    content = f"You scryed these {num_cards} cards: {', '.join(scryed_cards)}."
    await ctx.author.send(content)

    await ctx.author.send("Respond to me with a `!reorder` command with the re-ordered cards, separated by semicolons (;). To leave the deck in the same order you saw, simply run !reorder with no arguments.")

    game.waiting_for_response_from = MemberInfo(ctx.author.id, ctx.author.display_name, ctx.author.mention)
    game.waiting_for_response_action = 'reorder'
    game.waiting_for_response_number = num_cards
    save_game_state(RUNNING_GAMES)

    # if this was run outside the game channel, notify the game channel it happened
    game_channel = ctx.guild.get_channel(game.text_channel)
    if game_channel != ctx.channel:
        await game_channel.send(f"{ctx.author.mention} scryed {num_cards} cards")


@bot.command()
async def reorder(ctx: Context, *new_top_cards):
    """
    Re-order cards from a scry action

    Can only be used after a scry command was just run by the same player.
    Give the command the cards you're re-ordering in the order that you want them, separated by semicolons (;).
    If no argument is given, the re-order will resolve without changing the card order.
    """
    # re-join the words of the cards then split on the actual delimiter we're using
    new_top_cards = ' '.join(new_top_cards).split(LIST_DELIMITER)

    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")
        return

    if game.waiting_for_response_from.id and game.waiting_for_response_from.id != ctx.author.id:
        await ctx.send(f"I'm currently waiting to resolve an action ({game.waiting_for_response_action}) from player {game.waiting_for_response_from}, so no other actions can be taken")
        return

    if game.waiting_for_response_action != "reorder":
        await ctx.send(f"I'm currently waiting to resolve action {game.waiting_for_response_action}, so a re-order is not valid")
        return

    if game.waiting_for_response_number != len(new_top_cards):
        await ctx.send(f"I expected to be re-ordering {game.waiting_for_response_number} cards, but instead I got {len(new_top_cards)} {new_top_cards}. Was an extra semicolon added somewhere?")

    # At this point, we know it's the right player making a valid action type
    try:
        game.deck.reorder(new_top_cards)
    except ValueError as e:
        # send through the error if the list of cards doesn't line up with the top of the deck
        await ctx.send(e)
        return
    
    ctx.send("Cards successfully re-ordered")
    game.waiting_for_response_action = None
    game.waiting_for_response_from = None
    game.waiting_for_response_number = None


@bot.command()
async def play(ctx: Context, *card_words):
    """
    Play a card, sending it to the graveyard.

    Only cards drawn from the Deck of Death can be played this way.

    To buy back a card, use the !buyback command after !play-ing it
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")
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

    # if this was run outside the game channel, notify the game channel it happened
    game_channel = ctx.guild.get_channel(game.text_channel)
    if game_channel != ctx.channel:
        await game_channel.send(f"{ctx.author.mention} played {actual_card_name}")


@bot.command()
async def buyback(ctx: Context, *card_words):
    """
    Buy back a card, keeping it from the graveyard and leaving it playable.
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")
        return
    
    card_name = ' '.join(card_words)
    
    actual_card = game.graveyard.buyback(card_name)
    game.deck.buyback(card_name, member_id=ctx.author.id)

    save_game_state(RUNNING_GAMES)
    await ctx.send(f"{actual_card} has been bought back by {ctx.author.display_name}")


@bot.command()
async def flashback(ctx: Context, *card_words):
    """
    Play a card from the graveyard via Flashback

    Will only work if the card in question is both in the graveyard and has flashback
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")
        return

    card_name = ' '.join(card_words)

    try:
        actual_card = game.graveyard.flashback(card_name)
    except ValueError:
        await ctx.send(f"The card {card_name} was not found in the graveyard")
    
    game.exile.append(actual_card)
    save_game_state(RUNNING_GAMES)
    await ctx.send(f"{actual_card} has been flashbacked and is now exiled")


@bot.command()
async def resolve(ctx: Context, *card_words):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")
        return

    card_name = ' '.join(card_words)

    try:
        actual_card_name = game.deck.resolve(card_name)
    except ValueError:
        await ctx.send(f"{card_name} is not in the resolution stack")
    
    save_game_state(RUNNING_GAMES)
    
    await ctx.send(f"Resolved a copy of {actual_card_name}. The resolution stack is now: {game.deck._waiting_to_resolve}")


@bot.command()
async def hand(ctx: Context):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")
        return
    
    hand = game.deck.get_hand(member_id=ctx.author.id)
    if hand:
        hand_str = '\n'.join(hand)
        # TODO: include images?
        await ctx.author.send(f"The cards in your hand are:\n{hand_str}")
    else:
        await ctx.author.send(f"Your hand is empty!")


@bot.command()
async def decksize(ctx: Context):
    """
    Get the current size of the Deck of Death
    """
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.display_name} is currently playing in")
        return
    ctx.send(f"The Deck of Death has {len(game.deck.cards)} cards left")


@bot.command()
async def rules(ctx: Context):
    ctx.send("These still need to be defined :)")



def main():
    global RUNNING_GAMES
    RUNNING_GAMES = load_game_state()

    print("Running bot...")
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
