from disnake.utils import find

import os
from collections import defaultdict
from dataclasses import dataclass, field
from random import randint

def sanitize_card_name(card_name: str) -> str:
    """
    Sanitizes a card name to not include uppercase characters or quotes, to be used for comparison
    """
    return card_name.lower().replace('\'', '').replace('"', '')


@dataclass
class Deck():
    cards: list[str]
    _hands: dict[str, list[str]] = field(default_factory=lambda: {})
    _drawn_cards: list[str] = field(default_factory=lambda: [])
    # to hold OWD cards while waiting for them to resolve
    _waiting_to_resolve: list[str] = field(default_factory=lambda: [])

    def draw(self, member_id: int, num_cards: int=1) -> list[str]:
        """
        Returns and removes the top specified number of cards from the deck
        """
        # because when this goes into and out of JSON the keys become strings, this makes it easier to keep consistent state
        member_id_str = str(member_id)
        num_cards = min(num_cards, len(self.cards))
        drawn_cards = self.cards[:num_cards]
        self.cards = self.cards[num_cards:]

        normal_drawn_cards = [c for c in drawn_cards if c != 'One with Death']
        if member_id_str in self._hands:
            self._hands[member_id_str] = [*self._hands[member_id_str], *normal_drawn_cards]
        else:
            self._hands[member_id_str] = normal_drawn_cards
        self._waiting_to_resolve.extend([c for c in drawn_cards if c == 'One with Death'])

        print(self._hands)
        return drawn_cards


    def peek(self, num_cards: int) -> list[str]:
        """
        Returns without modifying some specified number of cards from the top of the deck
        """
        if len(self.cards) < num_cards:
            return self.cards
        else:
            return self.cards[:num_cards]


    def shuffle(self):
        """
        simple fisher-yates shuffle to mix up the cards
        """
        final_card_index = len(self.cards) - 1
        for i in range(len(self.cards) - 2):
            j = randint(i, final_card_index)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]


    def reorder(self, new_top_cards: list[str]):
        """
        Re-writes the top cards of the deck into the given group

        NOTE: this will throw an error if the new top cards are not the same as the inputted cards
        """
        curr_top_cards = self.cards[len(new_top_cards)]
        cards_match = [sanitize_card_name(c) for c in sorted(curr_top_cards)] != [(sanitize_card_name(c) for c in sorted(new_top_cards))]
        if not cards_match:
            raise ValueError("The list of re-ordered cards are not the same cards as in the deck.")
        
        # pull the formatted card name from the deck instead of the message to keep it looking clean
        new_top_cards_formatted = [
            [
                system_card_name
                for system_card_name in curr_top_cards
                if sanitize_card_name(system_card_name) == sanitize_card_name(user_card_name)
            ][0]
            for user_card_name
            in new_top_cards
        ]

        self.cards = [*new_top_cards_formatted, self.cards[len(new_top_cards):]]
    
        print(f"Swapped top cards in deck:\nOriginal: {curr_top_cards}\nNew: {new_top_cards_formatted}")


    def play(self, card: str, member_id: int) -> str:
        # because when this goes into and out of JSON the keys become strings, this makes it easier to keep consistent state
        member_id_str = str(member_id)

        card_indexes = [i for i, c in enumerate(self._hands.get(member_id_str, {})) if sanitize_card_name(c) == sanitize_card_name(card)]

        if not card_indexes:
            raise ValueError(f"Card {card} is not in your Deck of Death hand")

        card_to_return = self._hands[member_id].pop(card_indexes[0])

        return card_to_return


    def resolve(self, card: str) -> str:
        card_indexes = [i for i, c in enumerate(self._waiting_to_resolve) if sanitize_card_name(c) == sanitize_card_name(card)]

        if not card_indexes:
            raise ValueError(f"Card {card} is not in the cards waiting to be resolved from this Deck of Death")

        resolved_card = self._waiting_to_resolve.pop(card_indexes[0])
        if resolved_card == 'One with Death':
            self.cards.append(resolved_card)
            self.shuffle()

        return resolved_card
    

    def buyback(self, card: str, member_id: str):
        """
        Support the case of a buy-back where a card is playable again despite having just been played and thus removed
        """
        # because when this goes into and out of JSON the keys become strings, this makes it easier to keep consistent state
        member_id_str = str(member_id)

        if member_id_str in self._hands:
            self._hands[member_id_str].append(card)
        else:
            self._hands[member_id_str] = [card]


    def get_hand(self, member_id: str) -> list[str]:
        # because when this goes into and out of JSON the keys become strings, this makes it easier to keep consistent state
        member_id_str = str(member_id)
        if member_id_str in self._hands:
            return self._hands[member_id_str]
        else:
            return []


    @classmethod
    def from_file(cls, decklist_file: str, shuffle: bool=True):
        """
        Parses a deck from a decklist file, where each line specifies a count of a card then the card name, delimited by a space
        e.g. 11 One with Death
        """
        if not os.path.exists(decklist_file):
            raise FileNotFoundError(f"Could not find file {decklist_file} to initialize decklist")
        
        cards = []
        with open(decklist_file) as f:
            decklist = f.readlines()
        
        for line in decklist:
            delimiter_index = line.index(" ")

            num_cards, card_name = int(line[:delimiter_index]), line[delimiter_index + 1:] 
            cards.extend([card_name.strip()] * num_cards)
        
        deck = cls(cards=cards)

        if shuffle:
            deck.shuffle()
        
        return deck
