from dataclasses import dataclass
import json
import os
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
    return find(lambda m: m.id == member_id, RUNNING_GAMES)


@bot.command()
async def startgame(ctx: Context, *member_names_for_game: list[str]):
    if not ctx.guild:
        await ctx.send(f"You can only start the game from within the server where you want to play it")

    print(f"Starting new game for member {ctx.author.name}")
    game_members: list[Member] = [ctx.author]

    for member_name in member_names_for_game:
        members = await ctx.guild.search_members(member_name)

        if not any(members):
            await ctx.send(
                f'ERROR: Could not find member {member_name} in the server. Was there a typo, or were quotes (") forgotten around a name with spaces?'
            )
            return

        game_members.append(members[0])

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
        f"New channels created for a One With Death game hosted by {ctx.author.name}, including the players {', '.join([member.name for member in game_members[:-1]])} and {game_members[-1].name}"
    )

    game_state = OneWithDeathGame(
        id=f"owd-{ctx.author}",
        members=[
            MemberInfo(id=member.id, name=member.name, mention=member.mention)
            for member in game_members
        ],
        deck=Deck.from_file(DECKLIST_FILE, f"owd-{ctx.author.name}-library"),
        text_channel=text_channel.id,
        voice_channel=voice_channel.id,
        waiting_for_response_from=None
    )

    RUNNING_GAMES.append(game_state)
    save_game_state(RUNNING_GAMES)


@bot.command()
async def endgame(ctx: Context, game_id: Optional[str]=None):
    if not ctx.guild:
        await ctx.send(f"You can only end the game from the server where you're playing the game")

    # TODO: allow admins to manually specify game id, but only admins
    if not game_id:
        game_id = find_game_by_member_id(ctx.author.id).id
        if not game_id:
            # TODO: better error message
            await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.name} is currently playing in")

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
    if not ctx.guild:
        await ctx.send(f"You can only send game-changing commands (draw, scry, flashback, buyback, play) in the server where you're playing the game")

    try:
        num_cards = int(num_cards_str)
    except ValueError:
        await ctx.send(f"ERROR: {num_cards} is not a valid number")
        return
    
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.name} is currently playing in")
        return
    
    drawn_cards = game.deck.draw(num_cards)
    save_game_state(RUNNING_GAMES)
    
    # TODO: include card picture as attachment once I get them from danny
    content = f"You drew {'these' if num_cards > 1 else 'this'} {num_cards} card{'s' if num_cards > 1 else ''}: {', '.join(drawn_cards)}!"
    await ctx.author.send(content)

    game_channel = ctx.guild.get_channel(game.text_channel)
    if game_channel != ctx.channel:
        await game_channel.send(f"{ctx.author} drew {num_cards} cards")

    if any([True for c in drawn_cards if c == 'One With Death']):
        # TODO: Include OWD image here?
        await game_channel.send(f"{ctx.author} drew One With Death!")


@bot.command()
async def scry(ctx: Context, num_cards_str: str="1"):
    try:
        num_cards = int(num_cards_str)
    except ValueError:
        await ctx.send(f"ERROR: {num_cards} is not a valid number")
        return
    
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.name} is currently playing in")
        return
    
    if game.waiting_for_response_from.id:
        await ctx.send(f"Currently waiting to resolve an action ({game.waiting_for_response_action}) from player {game.waiting_for_response_from}, so no other actions can be taken")

    print(f"Scrying {num_cards} cards for {ctx.author} in game {game.id}")
    scryed_cards = game.deck.peek(num_cards)
    
    # TODO: where do I get card pictures from?
    content = f"You scryed these {num_cards} cards: {', '.join(scryed_cards)}. Here's their pictures:"
    await ctx.author.send(content)

    await ctx.author.send("Respond to me with a !reorder command with the re-ordered cards, separated by semicolons (;). To leave the deck in the same order you saw, simply run !reorder with no arguments.")

    game.waiting_for_response_from = MemberInfo(ctx.author.id, ctx.author.name, ctx.author.mention)
    game.waiting_for_response_action = 'reorder'
    game.waiting_for_response_number = num_cards
    save_game_state(RUNNING_GAMES)

    # if this was run outside the game channel, notify the game channel it happened
    game_channel = ctx.guild.get_channel(game.text_channel)
    if game_channel != ctx.channel:
        await game_channel.send(f"{ctx.author} scryed {num_cards} cards")


@bot.command()
async def reorder(ctx: Context, *new_top_cards: list[str]):
    """
    A command to allow a user that has just scried to re-order the cards they scried
    """
    # re-join the words of the cards then split on the actual delimiter we're using
    new_top_cards = ' '.join(new_top_cards).split(LIST_DELIMITER)

    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.name} is currently playing in")
        return

    if game.waiting_for_response_from.id and game.waiting_for_response_from.id != ctx.author.id:
        await ctx.send(f"I'm currently waiting to resolve an action ({game.waiting_for_response_action}) from player {game.waiting_for_response_from}, so no other actions can be taken")
        return

    if game.waiting_for_response_action != "reorder":
        await ctx.send(f"I'm currently waiting to resolve action {game.waiting_for_response_action}, so a re-order is not valid")
        return

    if game.waiting_for_response_number != len(new_top_cards):
        await ctx.send(f"I expected to be re-ordering {game.waiting_for_response_number} cards, but instead I got {len(new_top_cards)}. Was an extra semicolon added somewhere?")

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
async def play(ctx: Context):
    pass

@bot.command()
async def buyback(ctx: Context):
    pass

@bot.command()
async def flashback(ctx: Context):
    pass


@bot.command()
async def decksize(ctx: Context):
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        await ctx.send(f"Sorry, I couldn't find any games that {ctx.author.name} is currently playing in")
        return
    ctx.send(f"The Deck of Death has {len(game.deck.cards)} cards left")


def main():
    global RUNNING_GAMES
    RUNNING_GAMES = load_game_state()

    print("Running bot...")
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
