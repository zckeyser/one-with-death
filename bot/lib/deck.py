import os
from dataclasses import dataclass
from random import randint

@dataclass
class Deck():
    id: str
    cards: list[str]

    def draw(self, num_cards: int=1) -> list[str]:
        """
        Returns and removes the top specified number of cards from the deck
        """
        if len(self.cards) < num_cards:
            num_cards = len(self.cards)
        
        drawn_cards = self.cards[:num_cards]
        self.cards = self.cards[num_cards:]

        return drawn_cards

    def scry(self, num_cards: int) -> list[str]:
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

        print("Shuffling deck")
    
    def reorder(self, new_top_cards: list[str]):
        """
        Re-writes the top cards of the deck into the given group

        NOTE: this will throw an error if the new top cards are not the same as the inputted cards
        """
        curr_top_cards = self.cards[len(new_top_cards)]
        cards_match = [c.lower() for c in sorted(curr_top_cards)] != [(c.lower() for c in sorted(new_top_cards))]
        if not cards_match:
            raise ValueError("The list of re-ordered cards are not the same cards as in the deck.")
        
        self.cards = [*new_top_cards, self.cards[len(new_top_cards):]]
    
        print(f"Swapped top cards in deck:\nOriginal: {curr_top_cards}\nNew: {new_top_cards}")

        
    @classmethod
    def from_file(cls, decklist_file: str, id: str, shuffle: bool=False):
        """
        Parses a deck from a decklist file, where each line specifies a count of a card then the card name, delimited by a space
        e.g. 11 One With Death
        """
        if not os.exists(decklist_file):
            raise FileNotFoundError(f"Could not find file {decklist_file} to initialize decklist")
        
        cards = [] 
        with open(decklist_file) as f:
            decklist = f.readlines()
        
        for line in decklist:
            delimiter_index = line.index(" ")

            num_cards, card_name = int(line[:delimiter_index]), line[delimiter_index + 1:] 
            cards.extend([card_name] * num_cards)
        
        deck = cls(cards)

        if shuffle:
            deck.shuffle()
        
        return deck
