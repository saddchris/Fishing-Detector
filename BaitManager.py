import json
import time
from ctypes import wintypes

import cv2
import numpy as np
import pyautogui

from Paths import (
    SETTINGS_DIR,
    BAIT_IMAGES_DIR,
)

from WindowsInput import (
    is_key_down,
    send_scan_code,
    send_left_mouse_down,
    send_left_mouse_up,
)


VK_STOP = 0xDB
VK_START = 0xDD

SCAN_C = 0x2E


DEFAULT_MOVE_DURATION = 0.00
DEFAULT_MOUSE_SETTLE_DELAY = 0.010
DEFAULT_INVENTORY_OPEN_DELAY = 0.20
DEFAULT_MATCH_DETECTED_DELAY = 0.10
DEFAULT_LEFT_CLICK_HOLD = 0.05
DEFAULT_LEFT_CLICK_INTERVAL = 0.05
DEFAULT_AFTER_DOUBLE_CLICK_DELAY = 0.20


SETTINGS_FILE = (
    SETTINGS_DIR
    / "bait_manager_settings.json"
)


def _default_settings():
    return {
        "MOVE_DURATION": DEFAULT_MOVE_DURATION,
        "MOUSE_SETTLE_DELAY": DEFAULT_MOUSE_SETTLE_DELAY,
        "INVENTORY_OPEN_DELAY": DEFAULT_INVENTORY_OPEN_DELAY,
        "MATCH_DETECTED_DELAY": DEFAULT_MATCH_DETECTED_DELAY,
        "LEFT_CLICK_HOLD": DEFAULT_LEFT_CLICK_HOLD,
        "LEFT_CLICK_INTERVAL": DEFAULT_LEFT_CLICK_INTERVAL,
        "AFTER_DOUBLE_CLICK_DELAY": DEFAULT_AFTER_DOUBLE_CLICK_DELAY,
    }


def _load_settings():
    defaults = _default_settings()

    try:
        SETTINGS_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not SETTINGS_FILE.exists():

            with open(
                SETTINGS_FILE,
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    defaults,
                    file,
                    indent=4,
                )

            return defaults

        with open(
            SETTINGS_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            settings = json.load(file)

        if not isinstance(settings, dict):
            raise ValueError(
                "Settings file must contain a JSON object."
            )

        changed = False

        for key, default in defaults.items():

            if key not in settings:
                settings[key] = default
                changed = True

        for key in defaults:

            try:
                value = float(
                    settings[key]
                )

            except (
                TypeError,
                ValueError,
            ):

                value = defaults[key]
                changed = True

            if value < 0:
                value = defaults[key]
                changed = True

            settings[key] = value

        if changed:

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

        return settings

    except Exception as error:

        print(
            f"Could not load BaitManager settings: "
            f"{error}"
        )

        return defaults


BAIT_MANAGER_SETTINGS = _load_settings()


MOVE_DURATION = BAIT_MANAGER_SETTINGS[
    "MOVE_DURATION"
]

MOUSE_SETTLE_DELAY = BAIT_MANAGER_SETTINGS[
    "MOUSE_SETTLE_DELAY"
]

INVENTORY_OPEN_DELAY = BAIT_MANAGER_SETTINGS[
    "INVENTORY_OPEN_DELAY"
]

MATCH_DETECTED_DELAY = BAIT_MANAGER_SETTINGS[
    "MATCH_DETECTED_DELAY"
]

LEFT_CLICK_HOLD = BAIT_MANAGER_SETTINGS[
    "LEFT_CLICK_HOLD"
]

LEFT_CLICK_INTERVAL = BAIT_MANAGER_SETTINGS[
    "LEFT_CLICK_INTERVAL"
]

AFTER_DOUBLE_CLICK_DELAY = BAIT_MANAGER_SETTINGS[
    "AFTER_DOUBLE_CLICK_DELAY"
]


DEFAULT_MATCH_THRESHOLD = 0.75
SNAPPER_MATCH_THRESHOLD = 0.45
TIGER_REJECTION_THRESHOLD = 0.45

INVALID_BAIT_IMAGES = {
    "Screenshot_Tiger.png",
}

VALID_BAIT_IMAGES = {
    "Screenshot_Cod.png",
    "Screenshot_Gold.png",
    "Screenshot_Snapper.png",
    "Screenshot_Trout.png",
    "Screenshot_Tuna.png",
}

BAIT_MATCH_THRESHOLDS = {
    "Screenshot_Cod.png": DEFAULT_MATCH_THRESHOLD,
    "Screenshot_Gold.png": DEFAULT_MATCH_THRESHOLD,
    "Screenshot_Snapper.png": SNAPPER_MATCH_THRESHOLD,
    "Screenshot_Trout.png": DEFAULT_MATCH_THRESHOLD,
    "Screenshot_Tuna.png": DEFAULT_MATCH_THRESHOLD,
    "Screenshot_Tiger.png": TIGER_REJECTION_THRESHOLD,
}


last_bait_search_completed_without_match = False
c_held = False

bait_count = 0
bait_count_initialized = False


BAIT_POINTS = [
    (836, 810),
    (898, 810),
    (961, 810),
    (1022, 810),
    (1082, 810),
    (836, 870),
    (898, 870),
    (961, 870),
    (1022, 870),
    (1082, 870),
    (836, 930),
    (898, 930),
    (961, 930),
    (1022, 930),
    (1082, 933),
    (836, 990),
    (898, 990),
    (961, 990),
    (1022, 990),
    (1082, 990),
    (836, 1050),
    (898, 1050),
    (961, 1050),
    (1022, 1050),
    (1082, 1050),
]


bait_point_enabled = {
    point: True
    for point in BAIT_POINTS
}


BAIT_IMAGE_FOLDER = BAIT_IMAGES_DIR

BAIT_IMAGES = [
    "Screenshot_Cod.png",
    "Screenshot_Gold.png",
    "Screenshot_Snapper.png",
    "Screenshot_Trout.png",
    "Screenshot_Tuna.png",
    "Screenshot_Tiger.png",
]


SHOW_MATCH_WINDOW = True

MATCH_WINDOW_DELAY = 0.15

MATCH_WINDOW_TITLE = (
    "Bait Detection - Match / Confidence"
)

ACTUAL_SCREEN_WINDOW_TITLE = (
    "BAIT Detection - ACTUAL SCREEN"
)

MATCH_PREVIEW_SCALE = 4

TEXT_OFFSET_X = 0
TEXT_OFFSET_Y = -178

TEXT_CROP_WIDTH = 133
TEXT_CROP_HEIGHT = 32


def _send_scan_code(
    scan,
    key_up=False,
):

    send_scan_code(
        scan,
        key_up,
    )


def c_down():

    global c_held

    if c_held:
        return True

    try:

        _send_scan_code(
            SCAN_C,
            key_up=False,
        )

        c_held = True

        return True

    except Exception as error:

        print(
            f"C key down error: {error}"
        )

        return False


def c_up():

    global c_held

    if not c_held:
        return True

    try:

        _send_scan_code(
            SCAN_C,
            key_up=True,
        )

    except Exception as error:

        print(
            f"C key release error: {error}"
        )

    finally:

        c_held = False

    return True


def press_c():

    if not c_down():
        return False

    time.sleep(
        0.15
    )

    return c_up()


def left_mouse_down():

    send_left_mouse_down()


def left_mouse_up():

    send_left_mouse_up()


def double_left_click():

    left_mouse_down()

    time.sleep(
        LEFT_CLICK_HOLD
    )

    left_mouse_up()

    time.sleep(
        LEFT_CLICK_INTERVAL
    )

    left_mouse_down()

    time.sleep(
        LEFT_CLICK_HOLD
    )

    left_mouse_up()


def key_is_down(
    vk_code,
):

    return is_key_down(
        vk_code
    )


def stop_key_pressed():

    return key_is_down(
        VK_STOP
    )


def start_key_pressed():

    return key_is_down(
        VK_START
    )


def interruptible_sleep(
    duration,
    continue_check=None,
):

    end_time = (
        time.perf_counter()
        + max(
            0.0,
            duration,
        )
    )

    while (
        time.perf_counter()
        < end_time
    ):

        if stop_key_pressed():
            return False

        if (
            continue_check is not None
            and not continue_check()
        ):
            return False

        time.sleep(
            0.01
        )

    return True


def get_cursor_position():

    position = pyautogui.position()

    if position is None:

        raise RuntimeError(
            "Could not get cursor position."
        )

    point = wintypes.POINT()

    point.x = int(
        position.x
    )

    point.y = int(
        position.y
    )

    return (
        int(point.x),
        int(point.y),
    )


def set_cursor_position(
    x,
    y,
):

    pyautogui.moveTo(
        int(x),
        int(y),
        duration=0,
    )


def move_to_point(
    x,
    y,
    continue_check=None,
):

    if (
        continue_check is not None
        and not continue_check()
    ):
        return False

    if stop_key_pressed():
        return False

    pyautogui.moveTo(
        x,
        y,
        duration=MOVE_DURATION,
    )

    if (
        continue_check is not None
        and not continue_check()
    ):
        return False

    if stop_key_pressed():
        return False

    if not interruptible_sleep(
        MOUSE_SETTLE_DELAY,
        continue_check,
    ):
        return False

    get_cursor_position()

    return True


def get_bait_points():

    return list(
        BAIT_POINTS
    )


def get_enabled_bait_points():

    return [
        point
        for point in BAIT_POINTS
        if bait_point_enabled.get(
            point,
            True,
        )
    ]


def get_bait_point_enabled(
    point,
):

    point = (
        int(point[0]),
        int(point[1]),
    )

    return bait_point_enabled.get(
        point,
        True,
    )


def set_bait_point_enabled(
    point,
    enabled,
):

    point = (
        int(point[0]),
        int(point[1]),
    )

    if point not in bait_point_enabled:
        return False

    bait_point_enabled[
        point
    ] = bool(
        enabled
    )

    return True


def set_bait_point_enabled_by_index(
    point_number,
    enabled,
):

    try:

        point_number = int(
            point_number
        )

    except (
        TypeError,
        ValueError,
    ):

        return False

    if (
        point_number < 1
        or point_number > len(BAIT_POINTS)
    ):

        return False

    return set_bait_point_enabled(
        BAIT_POINTS[
            point_number - 1
        ],
        enabled,
    )


def get_bait_point_settings():

    return {
        f"{x},{y}": bool(
            bait_point_enabled[
                (x, y)
            ]
        )
        for x, y in BAIT_POINTS
    }


def set_bait_point_settings(
    settings,
):

    if not isinstance(
        settings,
        dict,
    ):

        return

    for index, point in enumerate(
        BAIT_POINTS,
        start=1,
    ):

        x, y = point

        keys = (
            f"{x},{y}",
            str(point),
            str(index),
        )

        found = False

        for key in keys:

            if key in settings:

                bait_point_enabled[
                    point
                ] = bool(
                    settings[key]
                )

                found = True

                break

        if not found:

            bait_point_enabled[
                point
            ] = True


def reset_bait_point_settings():

    for point in BAIT_POINTS:

        bait_point_enabled[
            point
        ] = True


def load_bait_images():

    templates = []

    for filename in BAIT_IMAGES:

        path = (
            BAIT_IMAGE_FOLDER
            / filename
        )

        template = cv2.imread(
            str(path),
            cv2.IMREAD_GRAYSCALE,
        )

        if template is None:

            print(
                f"Exception: Could not load bait image: "
                f"{path}"
            )

            continue

        templates.append(
            (
                filename,
                template,
            )
        )

    return templates


def get_text_crop(
    x,
    y,
):

    left = (
        x
        + TEXT_OFFSET_X
    )

    top = (
        y
        + TEXT_OFFSET_Y
    )

    screenshot = pyautogui.screenshot(
        region=(
            left,
            top,
            TEXT_CROP_WIDTH,
            TEXT_CROP_HEIGHT,
        )
    )

    image = cv2.cvtColor(
        np.array(screenshot),
        cv2.COLOR_RGB2GRAY,
    )

    return image


def get_match_threshold(
    filename,
):

    return BAIT_MATCH_THRESHOLDS.get(
        filename,
        DEFAULT_MATCH_THRESHOLD,
    )


def find_matching_bait(
    crop,
    templates,
):

    visual_scores = []

    for filename, template in templates:

        template_height, template_width = (
            template.shape
        )

        crop_height, crop_width = (
            crop.shape
        )

        if (
            template_height > crop_height
            or template_width > crop_width
        ):
            continue

        result = cv2.matchTemplate(
            crop,
            template,
            cv2.TM_CCOEFF_NORMED,
        )

        (
            _,
            maximum,
            _,
            maximum_location,
        ) = cv2.minMaxLoc(
            result
        )

        percentage = (
            max(
                0.0,
                maximum,
            )
            * 100
        )

        visual_scores.append(
            (
                filename,
                percentage,
                maximum_location,
                (
                    template_width,
                    template_height,
                ),
            )
        )

    if not visual_scores:

        return (
            None,
            0.0,
            None,
            None,
        )

    visual_scores.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    (
        strongest_filename,
        strongest_score,
        strongest_location,
        strongest_size,
    ) = visual_scores[0]

    strongest_threshold = (
        get_match_threshold(
            strongest_filename
        )
    )

    if (
        strongest_filename
        == "Screenshot_Tiger.png"
    ):

        return (
            None,
            0.0,
            strongest_location,
            strongest_size,
        )

    if (
        strongest_filename
        not in VALID_BAIT_IMAGES
    ):

        return (
            None,
            0.0,
            strongest_location,
            strongest_size,
        )

    if (
        strongest_score
        < strongest_threshold * 100
    ):

        return (
            None,
            0.0,
            strongest_location,
            strongest_size,
        )

    tiger_score = 0.0

    for (
        filename,
        percentage,
        location,
        size,
    ) in visual_scores:

        if (
            filename
            == "Screenshot_Tiger.png"
        ):

            tiger_score = percentage

            break

    if (
        tiger_score
        >= TIGER_REJECTION_THRESHOLD * 100
        and tiger_score
        >= strongest_score - 3.0
    ):

        return (
            None,
            0.0,
            strongest_location,
            strongest_size,
        )

    return (
        strongest_filename,
        strongest_score,
        strongest_location,
        strongest_size,
    )


def show_match_preview(
    crop,
    best_match,
    best_percentage,
    best_location,
    best_size,
    point_x=None,
    point_y=None,
):

    if not SHOW_MATCH_WINDOW:
        return

    try:

        preview = cv2.cvtColor(
            crop,
            cv2.COLOR_GRAY2BGR,
        )

        cv2.rectangle(
            preview,
            (0, 0),
            (
                preview.shape[1] - 1,
                preview.shape[0] - 1,
            ),
            (0, 255, 255),
            2,
        )

        if (
            best_location is not None
            and best_size is not None
        ):

            match_x, match_y = (
                best_location
            )

            match_width, match_height = (
                best_size
            )

            cv2.rectangle(
                preview,
                (
                    match_x,
                    match_y,
                ),
                (
                    match_x
                    + match_width
                    - 1,
                    match_y
                    + match_height
                    - 1,
                ),
                (0, 255, 0),
                2,
            )

        preview = cv2.resize(
            preview,
            None,
            fx=MATCH_PREVIEW_SCALE,
            fy=MATCH_PREVIEW_SCALE,
            interpolation=cv2.INTER_NEAREST,
        )

        label = (
            f"{best_match or 'NONE'} "
            f"{best_percentage:.1f}%"
        )

        cv2.rectangle(
            preview,
            (0, 0),
            (
                preview.shape[1],
                80,
            ),
            (0, 0, 0),
            -1,
        )

        cv2.putText(
            preview,
            label,
            (20, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        cv2.imshow(
            MATCH_WINDOW_TITLE,
            preview,
        )

        cv2.waitKey(1)

        if (
            point_x is not None
            and point_y is not None
        ):

            screen = pyautogui.screenshot()

            screen = cv2.cvtColor(
                np.array(screen),
                cv2.COLOR_RGB2BGR,
            )

            screen_height, screen_width = (
                screen.shape[:2]
            )

            crop_left = (
                int(point_x)
                + TEXT_OFFSET_X
            )

            crop_top = (
                int(point_y)
                + TEXT_OFFSET_Y
            )

            crop_right = (
                crop_left
                + TEXT_CROP_WIDTH
                - 1
            )

            crop_bottom = (
                crop_top
                + TEXT_CROP_HEIGHT
                - 1
            )

            crop_left = max(
                0,
                min(
                    crop_left,
                    screen_width - 1,
                ),
            )

            crop_top = max(
                0,
                min(
                    crop_top,
                    screen_height - 1,
                ),
            )

            crop_right = max(
                0,
                min(
                    crop_right,
                    screen_width - 1,
                ),
            )

            crop_bottom = max(
                0,
                min(
                    crop_bottom,
                    screen_height - 1,
                ),
            )

            cv2.rectangle(
                screen,
                (
                    crop_left,
                    crop_top,
                ),
                (
                    crop_right,
                    crop_bottom,
                ),
                (0, 0, 255),
                4,
            )

            cv2.circle(
                screen,
                (
                    int(point_x),
                    int(point_y),
                ),
                8,
                (255, 0, 0),
                -1,
            )

            cv2.imshow(
                ACTUAL_SCREEN_WINDOW_TITLE,
                screen,
            )

            cv2.waitKey(1)

        if MATCH_WINDOW_DELAY > 0:

            time.sleep(
                MATCH_WINDOW_DELAY
            )

    except Exception as error:

        print(
            f"Exception: match preview failed: "
            f"{error}"
        )


def close_match_preview():

    if not SHOW_MATCH_WINDOW:
        return

    try:

        cv2.destroyWindow(
            MATCH_WINDOW_TITLE
        )

        cv2.destroyWindow(
            ACTUAL_SCREEN_WINDOW_TITLE
        )

        cv2.waitKey(1)

    except Exception:
        pass


def check_point(
    point_number,
    x,
    y,
    templates,
    continue_check=None,
):

    if stop_key_pressed():

        return (
            None,
            0.0,
        )

    if (
        continue_check is not None
        and not continue_check()
    ):

        return (
            None,
            0.0,
        )

    crop = get_text_crop(
        x,
        y,
    )

    if stop_key_pressed():

        return (
            None,
            0.0,
        )

    if (
        continue_check is not None
        and not continue_check()
    ):

        return (
            None,
            0.0,
        )

    result = find_matching_bait(
        crop,
        templates,
    )

    (
        best_match,
        best_percentage,
        best_location,
        best_size,
    ) = result

    show_match_preview(
        crop,
        best_match,
        best_percentage,
        best_location,
        best_size,
        point_x=x,
        point_y=y,
    )

    return (
        best_match,
        best_percentage,
    )


def click_matched_slot(
    point_number,
    x,
    y,
    continue_check=None,
):

    if not interruptible_sleep(
        MATCH_DETECTED_DELAY,
        continue_check,
    ):

        return False

    set_cursor_position(
        x,
        y,
    )

    if not interruptible_sleep(
        MOUSE_SETTLE_DELAY,
        continue_check,
    ):

        return False

    actual_x, actual_y = (
        get_cursor_position()
    )

    if (
        actual_x != x
        or actual_y != y
    ):

        set_cursor_position(
            x,
            y,
        )

        if not interruptible_sleep(
            0.05,
            continue_check,
        ):

            return False

    if stop_key_pressed():
        return False

    if (
        continue_check is not None
        and not continue_check()
    ):

        return False

    double_left_click()

    if not interruptible_sleep(
        AFTER_DOUBLE_CLICK_DELAY,
        continue_check,
    ):

        return False

    return True


def return_to_fishing_position(
    fishing_position,
    continue_check=None,
):

    if fishing_position is None:
        return True

    fishing_x, fishing_y = (
        fishing_position
    )

    return move_to_point(
        fishing_x,
        fishing_y,
        continue_check,
    )


def get_bait_count():

    return bait_count


def is_bait_count_initialized():

    return bait_count_initialized


def reset_bait_count():

    global bait_count
    global bait_count_initialized
    global last_bait_search_completed_without_match

    bait_count = 0

    bait_count_initialized = False

    last_bait_search_completed_without_match = (
        False
    )


def set_bait_count(
    count,
):

    global bait_count
    global bait_count_initialized

    try:

        count = int(
            count
        )

    except (
        TypeError,
        ValueError,
    ):

        count = 0

    bait_count = max(
        0,
        count,
    )

    bait_count_initialized = True


def add_bait():

    global bait_count
    global bait_count_initialized

    bait_count += 1

    bait_count_initialized = True


def consume_bait():

    global bait_count

    if not bait_count_initialized:
        return False

    if bait_count <= 0:

        bait_count = 0

        return False

    bait_count -= 1

    if bait_count < 0:
        bait_count = 0

    return True


def did_last_bait_search_complete_without_match():

    return (
        last_bait_search_completed_without_match
    )


def equip_bait_if_available(
    continue_check,
    fishing_position=None,
):

    global last_bait_search_completed_without_match

    last_bait_search_completed_without_match = (
        False
    )

    templates = load_bait_images()

    if not templates:
        return False

    enabled_points = (
        get_enabled_bait_points()
    )

    if not enabled_points:

        print(
            "No bait points are enabled."
        )

        last_bait_search_completed_without_match = (
            True
        )

        return False

    first_x, first_y = (
        enabled_points[0]
    )

    if not move_to_point(
        first_x,
        first_y,
        continue_check,
    ):

        return False

    inventory_open = False

    search_completed = False

    try:

        if not c_down():
            return False

        inventory_open = True

        if not interruptible_sleep(
            INVENTORY_OPEN_DELAY,
            continue_check,
        ):

            return False

        for point_number, (
            x,
            y,
        ) in enumerate(
            BAIT_POINTS,
            start=1,
        ):

            if not get_bait_point_enabled(
                (x, y)
            ):

                continue

            if stop_key_pressed():
                return False

            if (
                continue_check is not None
                and not continue_check()
            ):

                return False

            if not move_to_point(
                x,
                y,
                continue_check,
            ):

                return False

            (
                best_match,
                best_percentage,
            ) = check_point(
                point_number,
                x,
                y,
                templates,
                continue_check,
            )

            if stop_key_pressed():
                return False

            if (
                continue_check is not None
                and not continue_check()
            ):

                return False

            if (
                best_match is not None
                and best_match
                in VALID_BAIT_IMAGES
            ):

                print(
                    f"PHYSICAL BAIT FOUND: "
                    f"{best_match}: "
                    f"{best_percentage:.1f}%"
                )

                if not click_matched_slot(
                    point_number,
                    x,
                    y,
                    continue_check,
                ):

                    return False

                last_bait_search_completed_without_match = (
                    False
                )

                if not return_to_fishing_position(
                    fishing_position,
                    continue_check,
                ):

                    return False

                return True

        search_completed = True

        last_bait_search_completed_without_match = (
            True
        )

        print(
            f"Bait count: {bait_count}"
        )

        if (
            bait_count_initialized
            and bait_count > 0
        ):

            if consume_bait():

                print(
                    f"Remaining: "
                    f"{bait_count}"
                )

                if not return_to_fishing_position(
                    fishing_position,
                    continue_check,
                ):

                    return False

                return True

        return_to_fishing_position(
            fishing_position,
            continue_check,
        )

        return False

    except Exception as error:

        print(
            f"Exception: bait handling failed: "
            f"{error}"
        )

        return False

    finally:

        if inventory_open:
            c_up()

        close_match_preview()