import json
import time

from Paths import SETTINGS_DIR

import numpy as np
from PIL import ImageGrab


SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

BUOY_WIDTH = 260
BUOY_HEIGHT = 260

left = (SCREEN_WIDTH - BUOY_WIDTH) // 2
top = (SCREEN_HEIGHT - BUOY_HEIGHT) // 2
right = left + BUOY_WIDTH
bottom = top + BUOY_HEIGHT

BUOY_REGION = (
    left,
    top,
    right,
    bottom,
)

SETTINGS_FILE = (
    SETTINGS_DIR
    / "buoy_detection_settings.json"
)

DEFAULT_SETTINGS = {
    "buoy_green_percentage": 5.0,
    "green_min": 40,
    "green_dominance": 1.10,
    "missed_red_percentage": 70.0,
    "red_min": 40,
    "red_dominance": 2.5,
    "bait_green_percentage": 0.1,
    "bait_green_dominance": 0.3,
    "bait_missed_red_percentage": 0.1,
    "bait_red_dominance": 0.3,
}


def load_settings():

    settings = DEFAULT_SETTINGS.copy()

    try:

        SETTINGS_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if SETTINGS_FILE.exists():

            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8",
            ) as file:

                saved_settings = json.load(
                    file
                )

            if isinstance(
                saved_settings,
                dict,
            ):

                for key in DEFAULT_SETTINGS:

                    if key in saved_settings:

                        settings[key] = (
                            saved_settings[key]
                        )

        else:

            with open(
                SETTINGS_FILE,
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    settings,
                    file,
                    indent=4,
                )

    except Exception as error:

        print(
            f"Could not load buoy detection "
            f"settings: {error}"
        )

    return settings


SETTINGS = load_settings()

BUOY_GREEN_PERCENTAGE = float(
    SETTINGS[
        "buoy_green_percentage"
    ]
)

GREEN_MIN = int(
    SETTINGS[
        "green_min"
    ]
)

GREEN_DOMINANCE = float(
    SETTINGS[
        "green_dominance"
    ]
)

MISSED_RED_PERCENTAGE = float(
    SETTINGS[
        "missed_red_percentage"
    ]
)

RED_MIN = int(
    SETTINGS[
        "red_min"
    ]
)

RED_DOMINANCE = float(
    SETTINGS[
        "red_dominance"
    ]
)

BAIT_GREEN_PERCENTAGE = float(
    SETTINGS[
        "bait_green_percentage"
    ]
)

BAIT_GREEN_DOMINANCE = float(
    SETTINGS[
        "bait_green_dominance"
    ]
)

BAIT_MISSED_RED_PERCENTAGE = float(
    SETTINGS[
        "bait_missed_red_percentage"
    ]
)

BAIT_RED_DOMINANCE = float(
    SETTINGS[
        "bait_red_dominance"
    ]
)

DETECTION_INTERVAL = 0.01


def get_buoy_colors():

    screenshot = ImageGrab.grab(
        bbox=BUOY_REGION
    )

    img_array = np.array(
        screenshot
    )

    r = img_array[:, :, 0]
    g = img_array[:, :, 1]
    b = img_array[:, :, 2]

    return (
        r,
        g,
        b,
    )


def calculate_green_percentage(
    r,
    g,
    b,
    dominance=GREEN_DOMINANCE,
):

    green_mask = (
        (g >= GREEN_MIN)
        & (
            g
            > r * dominance
        )
        & (
            g
            > b * dominance
        )
    )

    green_pixels = np.count_nonzero(
        green_mask
    )

    total_pixels = r.size

    if total_pixels == 0:
        return 0.0

    return (
        green_pixels
        / total_pixels
    ) * 100.0


def calculate_red_percentage(
    r,
    g,
    b,
    dominance=RED_DOMINANCE,
):

    red_mask = (
        (r >= RED_MIN)
        & (
            r
            > g * dominance
        )
        & (
            r
            > b * dominance
        )
    )

    red_pixels = np.count_nonzero(
        red_mask
    )

    total_pixels = r.size

    if total_pixels == 0:
        return 0.0

    return (
        red_pixels
        / total_pixels
    ) * 100.0


def check_buoy_green(
    green_percentage_threshold=BUOY_GREEN_PERCENTAGE,
    green_dominance=GREEN_DOMINANCE,
):

    r, g, b = get_buoy_colors()

    percentage = calculate_green_percentage(
        r,
        g,
        b,
        dominance=green_dominance,
    )

    return (
        percentage >= green_percentage_threshold,
        percentage,
    )


def check_buoy_missed(
    red_percentage_threshold=MISSED_RED_PERCENTAGE,
    red_dominance=RED_DOMINANCE,
):

    r, g, b = get_buoy_colors()

    percentage = calculate_red_percentage(
        r,
        g,
        b,
        dominance=red_dominance,
    )

    return (
        percentage >= red_percentage_threshold,
        percentage,
    )


def check_buoy(
    bait_equipped=False,
):

    if bait_equipped:

        green_threshold = (
            BAIT_GREEN_PERCENTAGE
        )

        green_dominance = (
            BAIT_GREEN_DOMINANCE
        )

        red_threshold = (
            BAIT_MISSED_RED_PERCENTAGE
        )

        red_dominance = (
            BAIT_RED_DOMINANCE
        )

    else:

        green_threshold = (
            BUOY_GREEN_PERCENTAGE
        )

        green_dominance = (
            GREEN_DOMINANCE
        )

        red_threshold = (
            MISSED_RED_PERCENTAGE
        )

        red_dominance = (
            RED_DOMINANCE
        )

    r, g, b = get_buoy_colors()

    green_percentage = (
        calculate_green_percentage(
            r,
            g,
            b,
            dominance=green_dominance,
        )
    )

    if (
        green_percentage
        >= green_threshold
    ):

        return (
            "green",
            green_percentage,
        )

    red_percentage = (
        calculate_red_percentage(
            r,
            g,
            b,
            dominance=red_dominance,
        )
    )

    if (
        red_percentage
        >= red_threshold
    ):

        return (
            "missed",
            red_percentage,
        )

    return (
        None,
        0.0,
    )


def wait_for_buoy(
    enabled_callback,
    bait_equipped=False,
):

    while enabled_callback():

        state, percentage = (
            check_buoy(
                bait_equipped=bait_equipped
            )
        )

        if state == "green":

            print(
                f"GREEN: {percentage:.2f}%"
            )

            return "green"

        if state == "missed":

            print(
                f"RED: {percentage:.2f}%"
            )

            return "missed"

        time.sleep(
            DETECTION_INTERVAL
        )

    return False
