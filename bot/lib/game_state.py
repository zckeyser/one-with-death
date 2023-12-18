import os
import json

from constants import GAME_STATE_FILE
from models import OneWithDeathGame


def save_game_state(games: list[OneWithDeathGame]):
    with open(GAME_STATE_FILE, 'w') as f:
        json_serializable_games = [game.to_dict() for game in games]
        json.dump(json_serializable_games, f)


def load_game_state() -> list[OneWithDeathGame]:
    if not os.exists(GAME_STATE_FILE):
        return []
    with open(GAME_STATE_FILE, 'r') as f:
        game_dicts = json.load(f)

        return [OneWithDeathGame.from_dict(d) for d in game_dicts]
