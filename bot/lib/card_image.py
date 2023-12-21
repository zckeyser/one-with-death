import os

from constants import CARD_IMAGES_FOLDER
from errors import ImageNotFoundError
from lib.util import sanitize_card_name


def card_name_to_snake_case(card_name: str) -> str:
    return sanitize_card_name(card_name).replace(' ', '_')


def get_image_file_location(card_name: str) -> str:
    image_file_path = os.path.join(CARD_IMAGES_FOLDER, f"{card_name_to_snake_case(card_name)}.png")
    if not os.path.exists(image_file_path):
        raise ImageNotFoundError(f"No image file found at {image_file_path}")
    return image_file_path
