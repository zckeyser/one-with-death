from dataclasses import dataclass
import json
import os

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


def main():
    global RUNNING_GAMES
    RUNNING_GAMES = load_game_state()

    print("Running bot...")
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
