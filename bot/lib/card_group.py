from abc import ABC
from dataclasses import dataclass
from typing import Optional
from lib.util import sanitize_card_name


class CardGroup(ABC):
    cards: list[str]

    def find(self, card_name: str) -> Optional[str]:
        found_cards = [c for c in self.cards if sanitize_card_name(c) == sanitize_card_name(card_name)]

        if not found_cards:
            return None
        else:
            return found_cards[0]

    def index(self, card_name: str) -> Optional[int]:
        found_cards = [i for i, c in enumerate(self.cards) if sanitize_card_name(c) == sanitize_card_name(card_name)]

        if not found_cards:
            return None
        else:
            return found_cards[0]
