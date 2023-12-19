import os
from dataclasses import dataclass, field
from random import randint

from lib.util import sanitize_card_name


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


    def reorder_scry(self, new_top_card_indexes: list[int], new_bottom_card_indexes: list[int]):
        """
        Re-writes the top cards of the deck into the given order, re-grouping cards on either or both of the top or bottom of the deck.

        NOTE: this will throw an error if the card indexes do not contain 1..n, where n is the total number of card submitted for re-ordering.
        """
        expected_card_indexes = [i + 1 for i in range(len(new_top_card_indexes) + len(new_bottom_card_indexes))]
        total_card_indexes = sorted([*new_top_card_indexes, *new_bottom_card_indexes])

        if expected_card_indexes != total_card_indexes:
            raise ValueError(f"Invalid card indexes for rearrange re-ordering provided: {[i for i in total_card_indexes if i not in expected_card_indexes]}")

        # grab the slices to put on top and bottom
        # the indexes provided by users are 1-based for easier usability
        new_top_cards = [self.cards[i - 1] for i in new_top_card_indexes]
        new_bottom_cards = [self.cards[i - 1] for i in new_bottom_card_indexes]

        # chop off the cards being re-ordered from the top
        self.cards = self.cards[len(total_card_indexes):]
        self.cards = [*new_top_cards, *self.cards, *new_bottom_cards]

        print(f"Re-ordered {len(total_card_indexes)} cards as a scry re-order")


    def reorder_rearrange(self, new_top_card_indexes: list[int]):
        """
        Re-writes the top cards of the deck into the given order, only allowing cards to go to the top of the deck.

        NOTE: this will throw an error if the card indexes do not contain 1..n, where n is the total number of card submitted for re-ordering.
        """
        expected_card_indexes = [i + 1 for i in range(len(new_top_card_indexes))]

        if expected_card_indexes != sorted(new_top_card_indexes):
            raise ValueError(f"Invalid card indexes for rearrange re-ordering provided: {[i for i in new_top_card_indexes if i not in expected_card_indexes]}")

        # grab the slice to put on top 
        # the indexes provided by users are 1-based for easier usability
        new_top_cards = [self.cards[i - 1] for i in new_top_card_indexes]

        # chop off the cards being re-ordered from the top
        self.cards = self.cards[len(new_top_card_indexes):]
        self.cards = [*new_top_cards, *self.cards]

        print(f"Re-ordered {len(new_top_card_indexes)} cards as a rearrange re-order")


    def play(self, card: str, member_id: int) -> str:
        # because when this goes into and out of JSON the keys become strings, this makes it easier to keep consistent state
        member_id_str = str(member_id)

        card_indexes = [i for i, c in enumerate(self._hands.get(member_id_str, {})) if sanitize_card_name(c) == sanitize_card_name(card)]

        if not card_indexes:
            raise ValueError(f"Card {card} is not in your Deck of Death hand")

        card_to_return = self._hands[member_id_str].pop(card_indexes[0])

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
    

    def buyback(self, card: str, member_id: int):
        """
        Support the case of a buy-back where a card is playable again despite having just been played and thus removed
        """
        # because when this goes into and out of JSON the keys become strings, this makes it easier to keep consistent state
        member_id_str = str(member_id)

        if member_id_str in self._hands:
            self._hands[member_id_str].append(card)
        else:
            self._hands[member_id_str] = [card]


    def get_hand(self, member_id: int) -> list[str]:
        # because when this goes into and out of JSON the keys become strings, this makes it easier to keep consistent state
        member_id_str = str(member_id)
        if member_id_str in self._hands:
            return self._hands[member_id_str]
        else:
            return []


    def add_card_to_hand(self, member_id: int, card_name: str):
        # because when this goes into and out of JSON the keys become strings, this makes it easier to keep consistent state
        member_id_str = str(member_id)
        if member_id_str in self._hands:
            self._hands[member_id_str].append(card_name)
        else:
            self._hands[member_id_str] = [card_name]


    @classmethod
    def from_file(cls, decklist_file: str, member_ids: list[int]=None, shuffle: bool=True):
        """
        Parses a deck from a decklist file, where each line specifies a count of a card then the card name, delimited by a space
        e.g. 11 One with Death
        """
        if not member_ids:
            member_ids = []

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
        
        for member_id in member_ids:
            deck.add_card_to_hand(member_id=member_id, card_name="Nix")

        return deck
