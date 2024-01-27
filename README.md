# One With Death Discord Bot

Discord bot to serve as a helper for games of the One With Death format created by John and Dan from [Comfort Zone Commander](https://www.youtube.com/@comfortzonecommander).

# Rules

TBD, get these from Dan.

# Bot Usage

An instance of the bot can be run fairly simply by following these directions:

1. Create a file in the root of this repo called api_key.txt. It should contain only your API key for Discord.
2. Create a file in the root of this repo called oauth_secret.txt. It should contain only your OAuth secret credential for Discord.
3. Create a virtual environment with `python -m virtualenv .venv`
4. Enter the virtual environment using `source .venv/bin/activate` on Bash on Linux, `source .venv/Scripts/activate` on Bash on Windows, or `./.venv/Scripts/activate.ps1` on Powershell on Windows.
5. Install the project requirements via `pip install -r requirements.txt`
6. Run the bot script: `python bot/bot.py`