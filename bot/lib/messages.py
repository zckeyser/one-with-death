from disnake.ext.commands.context import Context
from models import OneWithDeathGame

async def send_game_channel_warning_message(ctx: Context, game: OneWithDeathGame):
    # can only get the channel name if we have the guild because we're only saving the ID
    # TODO: save the channel name too when starting game and just grab it off the save
    if ctx.guild:
        expected_channel_text = f" ({ctx.guild.get_channel(game.text_channel).name})"
    await ctx.send(f"You can only send public game-changing commands in the channel where you're playing the game{expected_channel_text}")
