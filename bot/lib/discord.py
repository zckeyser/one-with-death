
from disnake.ext.commands.context import Context
from models import OneWithDeathGame

def message_is_in_server(ctx: Context) -> bool:
    return bool(ctx.guild)

def message_is_in_game_channel(ctx: Context, game: OneWithDeathGame) -> bool:
    return ctx.guild and ctx.channel.id == game.text_channel
