import os

import enum
from functools import cache

from constants import CARD_LIST_FILE_TEMPLATE


class CardListCategory(enum.Enum):
    BUYBACK = 'buyback'
    FLASHBACK = 'flashback'


@cache
def get_card_list(category: str):
    """
    Get a list of cards specified for some category.

    Card lists should be in a {category}_cards.txt file in the bot/resources folder,
    with one card name on each line.
    """
    filename = CARD_LIST_FILE_TEMPLATE.format(category=category)
    with open(filename, 'r') as f:
        return [line.strip() for line in f.readlines()]
