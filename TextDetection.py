import cv2
import pyautogui
import numpy as np

from Paths import CONFIG_IMAGES_DIR


TEMPLATE = CONFIG_IMAGES_DIR / "InventoryFull.png"
MATCH_THRESHOLD = 0.90


def detect_inventory_full():

    template = cv2.imread(
        str(TEMPLATE),
        cv2.IMREAD_GRAYSCALE,
    )

    if template is None:
        raise FileNotFoundError(
            f"Could not open {TEMPLATE}"
        )

    screenshot = pyautogui.screenshot()

    screen_image = cv2.cvtColor(
        np.array(screenshot),
        cv2.COLOR_RGB2GRAY,
    )

    if (
        template.shape[0] > screen_image.shape[0]
        or template.shape[1] > screen_image.shape[1]
    ):
        print(
            "Inventory text detection: 0.0% "
            "(template larger than screen)"
        )
        return False

    result = cv2.matchTemplate(
        screen_image,
        template,
        cv2.TM_CCOEFF_NORMED,
    )

    _, maximum, _, _ = cv2.minMaxLoc(
        result
    )

    percentage = (
        max(0.0, maximum)
        * 100
    )

    print(
        f"Inventory text detection: "
        f"{percentage:.1f}%"
    )

    if maximum >= MATCH_THRESHOLD:
        print(
            "Inventory text detection: MATCH"
        )
        return True

    return False