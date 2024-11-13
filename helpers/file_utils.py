import json
import os
from core.config import logger


def load_archive(filename: str) -> dict:
    """Load JSON archive file"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error loading {filename}, returning empty dict")
            return {}
    return {}


def save_archive(data: dict, filename: str) -> None:
    """Save data to JSON archive file"""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved data to {filename}")
