from dataclasses import dataclass, field
from functools import cache

from errors import CardMissingBuybackError, CardMissingFlashbackError, CardNotFoundError
from lib.card_lists import get_card_list
from lib.card_group import CardGroup
from lib.util import find_card_index


@dataclass
class Graveyard(CardGroup):
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


    def pull_card_by_name(self, card_name: str) -> str:
        card_in_grave_index = find_card_index(card_name, self.cards)
        if card_in_grave_index < 0:
            raise CardNotFoundError(f"Card {card_name} cannot be pulled because it is not in the graveyard")
        
        return self.cards.pop(card_in_grave_index)


    def pull_card_by_index(self, card_index: int) -> str:
        if card_index < 0 or card_index > len(self.cards):
            raise IndexError()
        
        return self.cards.pop(card_index)


    def get_recurrable_cards(self) -> list[str]:
        """
        Get a list of cards currently in the graveyard with a recurrence effect.
        """
        flashback_cards = get_card_list("flashback")
        recur_cards = get_card_list("recur")

        return [c for c in self.cards if c in flashback_cards or c in recur_cards]


    def __len__(self) -> int:
        return len(self.cards)
