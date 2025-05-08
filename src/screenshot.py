import pyautogui
from uuid import uuid4
from datetime import datetime


def take_screenshot() -> str:
    """Takes a screenshot and returns the path for the file."""
    image = pyautogui.screenshot()
    # path = "./" + datetime.now().isoformat(timespec="seconds") + ".jpg"
    path = str(uuid4()) + ".jpg"
    image.save(path)
    return path
