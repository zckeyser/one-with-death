def format_card_list(cards: list[str], include_numbers: bool=False) -> str:
    """
    Formats a list of cards to be displayed in a one-per-line fashion in a code block, using markdown syntax
    """
    cards_str = '\n'.join([
        f"{(i + 1) + '. ' if include_numbers else ''}{card_name}"
        for i, card_name
        in enumerate(cards)
    ])
    return f"""```
{cards_str}
```"""