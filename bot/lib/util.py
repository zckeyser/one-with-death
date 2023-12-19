def sanitize_card_name(card_name: str) -> str:
    """
    Sanitizes a card name to not include uppercase characters or quotes, to be used for comparison
    """
    return card_name.lower().replace('\'', '').replace('"', '')


def find_card_index(card_name: str, card_list: str) -> int:
    """
    Finds the index of a card in the list of cards, comparing sanitized card names rather than the literal value.

    Returns -1 if the card is not found.
    """
    card_index = [i for i, grave_card in enumerate(card_list) if grave_card.lower() == card_name.lower()]

    return card_index[0] if len(card_index) > 0 else -1
