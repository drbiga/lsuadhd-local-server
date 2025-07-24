import os
import uuid
import mss
import win32api
from PIL import Image

# Assume this is defined globally
SCREENSHOT_DIR = "screenshots"


def take_screenshot():
    with mss.mss() as sct:
        mouse_x, mouse_y = win32api.GetCursorPos()

        # Find which monitor the mouse is on
        monitor_index = 1  # default to first monitor if none matched
        for i, monitor in enumerate(sct.monitors[1:], start=1):
            if (
                monitor["left"] <= mouse_x < monitor["left"] + monitor["width"]
                and monitor["top"] <= mouse_y < monitor["top"] + monitor["height"]
            ):
                monitor_index = i
                break

        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)

        filename = f"{uuid.uuid4()}.png"
        filepath = os.path.join(SCREENSHOT_DIR, filename)

        img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        img.save(filepath)

        return filepath
