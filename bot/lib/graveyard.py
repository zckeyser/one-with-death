from dataclasses import dataclass, field
from functools import cache

@dataclass
class Graveyard():
    cards: list[str] = field(default_factory=lambda: list())

    def insert(self, card: str):
        self.cards.append(card)
    
    def flashback(self, card: str) -> str:
        card_in_grave_index = [i for i, grave_card in enumerate(self.cards) if grave_card.lower() == card.lower()]
        if len(card_in_grave_index) == 0:
            raise ValueError(f"Card {card} cannot be flashbacked because it is not in the graveyard")
        
        # TODO: check if card actually has flashback before letting them do this
        return self.cards.pop(card_in_grave_index)
