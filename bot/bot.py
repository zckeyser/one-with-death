from dataclasses import dataclass
import os

import disnake
from disnake.channel import TextChannel, VoiceChannel
from disnake.ext import commands
from disnake.ext.commands.context import Context
from disnake.member import Member

from models import Card, MemberInfo, OneWithDeathGame

running_games = {}

intents = disnake.Intents.default()
intents.message_content = True
intents.members = True

with open("api_key.txt", "r") as f:
    TOKEN = f.read()

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

    game_state = GameState


@bot.command()
async def ping(ctx):
    await ctx.send("Pong")


print("Running bot...")
bot.run(TOKEN)
