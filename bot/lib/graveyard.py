from dataclasses import dataclass, field
from functools import cache

from errors import CardMissingBuybackError, CardMissingFlashbackError, CardNotFoundError
from lib.card_lists import get_card_list
from lib.util import find_card_index, sanitize_card_name





@dataclass
class Graveyard():
    cards: list[str] = field(default_factory=lambda: list())

    def insert(self, card: str):
        self.cards.append(card)


    def buyback(self, card_name: str):
        card_in_grave_index = find_card_index(card_name, self.cards)
        if card_in_grave_index < 0:
            raise CardNotFoundError(f"Card {card_name} cannot be flashbacked because it is not in the graveyard")

        actual_card_name = self.cards[card_in_grave_index]
        buyback_cards = get_card_list("buyback")

        if actual_card_name not in buyback_cards:
            raise CardMissingBuybackError(f"{actual_card_name} doesn't have buyback")
        
        return self.cards.pop(card_in_grave_index)


    def flashback(self, card_name: str) -> str:
        card_in_grave_index = find_card_index(card_name, self.cards)
        if card_in_grave_index < 0:
            raise CardNotFoundError(f"Card {card_name} cannot be flashbacked because it is not in the graveyard")

        actual_card_name = self.cards[card_in_grave_index]
        flashback_cards = get_card_list("flashback")

        if actual_card_name not in flashback_cards:
            raise CardMissingFlashbackError(f"{actual_card_name} doesn't have flashback")
        
        return self.cards.pop(card_in_grave_index)


    def get_recurrable_cards(self) -> list[str]:
        """
        Get a list of cards currently in the graveyard with a recurrence effect.
        """
        flashback_cards = get_card_list("flashback")

        return [c for c in self.cards if c in flashback_cards]
