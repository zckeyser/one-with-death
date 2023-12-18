import disnake
from disnake.ext import commands

intents = disnake.Intents.default()
intents.message_content = True

with open("api_key.txt", "r") as f:
    TOKEN = f.read()

from disnake.ext import commands

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command()
async def test(ctx, arg):
    await ctx.send(arg)

bot.run(TOKEN)
