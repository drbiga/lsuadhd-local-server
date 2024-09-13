import pyautogui
from uuid import uuid4

def take_screenshot() -> str:
    """Takes a screenshot and returns the path for the file."""
    image = pyautogui.screenshot()
    path = str(uuid4()) + '.jpg'
    image.save(path)
    return path
