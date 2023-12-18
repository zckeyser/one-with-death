import os


def _get_filepath_relative_to_this_file(rel_filepath: str) -> str:
    return os.path.realpath(os.path.join(os.path.dirname(__file__), rel_filepath))

DECKLIST_FILE = _get_filepath_relative_to_this_file("../resources/decklist.txt")
GAME_STATE_FILE = _get_filepath_relative_to_this_file("../state/game_state.json")

LIST_DELIMITER = ';'
