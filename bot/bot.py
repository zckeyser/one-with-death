from dataclasses import dataclass
import json
import os
from typing import Optional

import disnake
from disnake.channel import TextChannel, VoiceChannel
from disnake.ext import commands
from disnake.ext.commands.context import Context
from disnake.member import Member

from constants import DECKLIST_FILE
from lib.deck import Deck
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


def find_game_by_member_id(member_id: str) -> OneWithDeathGame:
    games_with_member = [
        game for game in RUNNING_GAMES if any([member.id for member in game if member.id == member_id])
    ]
    if games_with_member:
        if len(games_with_member) > 1:
            print(f"WARNING: member {member_id} is in multiple games, which is not supported and could cause problems")

        return games_with_member[0]


@bot.command()
async def startgame(ctx: Context, *member_names_for_game):
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

    text_channel_name = f"one-with-death-{ctx.author}"
    print(f"Creating text channel {text_channel_name}")
    text_channel: TextChannel = await ctx.guild.create_text_channel(
        text_channel_name, overwrites=overwrites
    )

    voice_channel_name = f"one-with-death-vc-{ctx.author}"
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
        library=Deck.from_file(DECKLIST_FILE),
        text_channel=text_channel.id,
        voice_channel=voice_channel.id,
        waiting_for_response_from=None
    )

    RUNNING_GAMES.append(game_state)
    save_game_state(RUNNING_GAMES)


@bot.command()
def endgame(ctx: Context, game_id: Optional[str]=None):
    # TODO: allow admins to manually specify game id, but only admins
    if not game_id:
        game_id = find_game_by_member_id(ctx.author.id).id
        if not game_id:
            # TODO: better error message
            ctx.send(f"Sorry, I couldn't find any games that {ctx.author.name} is currently playing in")

    game_index_list = [i for i, g in enumerate(RUNNING_GAMES) if g.id == game_id]

    if not game_index_list:
        ctx.send(f"Game with id {game_id} was not found")
    else:
        game_index = game_index_list[0]
        game = RUNNING_GAMES[0]
        global RUNNING_GAMES
        RUNNING_GAMES = [*RUNNING_GAMES[:game_index], *RUNNING_GAMES[game_index:]]
        save_game_state(RUNNING_GAMES)

        ctx.guild.get_channel(game.text_channel).delete()
        ctx.guild.get_channel(game.voice_channel).delete()


@bot.command()
def draw(ctx: Context, num_cards_str: str="1"):
    try:
        num_cards = int(num_cards_str)
    except ValueError:
        ctx.send(f"ERROR: {num_cards} is not a valid number")
    
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        ctx.send(f"Sorry, I couldn't find any games that {ctx.author.name} is currently playing in")
        return
    
    drawn_cards = game.library.draw(num_cards)
    save_game_state(RUNNING_GAMES)
    
    # TODO: where do I get card pictures from?
    content = f"You drew these {num_cards} cards: {', '.join(drawn_cards)}. Here's their pictures:"
    ctx.author.send(content)

    game_channel = ctx.guild.get_channel(game.text_channel)
    if game_channel != ctx.channel:
        game_channel.send(f"{ctx.author} drew {num_cards} cards")


@bot.command()
def scry(ctx: Context, num_cards_str: str="1"):
    try:
        num_cards = int(num_cards_str)
    except ValueError:
        ctx.send(f"ERROR: {num_cards} is not a valid number")
    
    game = find_game_by_member_id(ctx.author.id)
    if not game:
        ctx.send(f"Sorry, I couldn't find any games that {ctx.author.name} is currently playing in")
        return
    
    scryed_cards = game.library.scry(num_cards)
    
    # TODO: where do I get card pictures from?
    content = f"You scryed these {num_cards} cards: {', '.join(scryed_cards)}. Here's their pictures:"
    ctx.author.send(content)

    game_channel = ctx.guild.get_channel(game.text_channel)
    if game_channel != ctx.channel:
        game_channel.send(f"{ctx.author} scryed {num_cards} cards")


def main():
    global RUNNING_GAMES
    RUNNING_GAMES = load_game_state()

    print("Running bot...")
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
