import os
import json

from constants import GAME_STATE_FILE
from models import OneWithDeathGame


def save_game_state(games: list[OneWithDeathGame]):
    print(games)
    original_state = load_game_state()
    try:
        with open(GAME_STATE_FILE, 'w') as f:
            json_serializable_games = [game.to_dict() for game in games]
            json.dump(json_serializable_games, f, indent=4)
    except:
        # if we fail to save the new changes, fall back to whatever was there before, if anything
        if original_state:
            with open(GAME_STATE_FILE, 'w') as f:
                json.dump(original_state, f, indent=4)
        else:
            # there was no existing state, so remove the file created during the faulty save
            if os.path.exists(GAME_STATE_FILE):
                os.remove(GAME_STATE_FILE)
        # still raise the error so we know there's an issue
        raise


def load_game_state() -> list[OneWithDeathGame]:
    if not os.path.exists(GAME_STATE_FILE):
        print("No existing game state found, starting with empty state")
        return []
    try:
        with open(GAME_STATE_FILE, 'r') as f:
            game_dicts = json.load(f)

            print(f"Found {len(game_dicts)} existing games upon load")

            return [OneWithDeathGame.from_dict(d) for d in game_dicts]
    except Exception as e:
        # TODO: use a logger you lazy bastard
        print('ERROR WHILE LOADING GAME STATE: ', e)
        return []
