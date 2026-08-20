import gc
import threading
import time
import winsound
import pyautogui

from BuoyDetector import wait_for_buoy as wait_for_buoy_original
from Detection import FishDetector
from TextDetection import detect_inventory_full
import BaitManager
from WindowsInput import (
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_RIGHTDOWN,
    MOUSEEVENTF_RIGHTUP,
    is_key_down as windows_is_key_down,
    send_mouse_input,
    send_scan_code,
)

ESCAPE_KEY = "esc"
VK_ESCAPE = 0x1B
VK_RIGHT_BRACKET = 0xDD
SCAN_E = 0x12
SCAN_R = 0x13

UNKNOWN_DING_FREQUENCY = 1000
UNKNOWN_DING_DURATION = 250
INVENTORY_FULL_FREQUENCY = 500
INVENTORY_FULL_DURATION = 700

FISHING_STALL_TIMEOUT = 30.0

detector = None
enabled = False
right_mouse_held = False
shutdown_requested = False
values_loaded = False
auto_bait_enabled = False
bait_check_allowed = True
bait_inventory_scan_exhausted = False

fishing_thread = None
stop_event = threading.Event()
failsafe_stop_event = threading.Event()
state_lock = threading.RLock()
failsafe_thread = None
state_callback = None
exit_callback = None


def _safe_print(message=""):
    try:
        print(message)
    except Exception:
        pass


def set_state_callback(callback):
    global state_callback

    with state_lock:
        state_callback = callback


def set_exit_callback(callback):
    global exit_callback

    with state_lock:
        exit_callback = callback


def set_auto_bait_enabled(enabled_value):
    global auto_bait_enabled
    global bait_check_allowed
    global bait_inventory_scan_exhausted

    with state_lock:
        auto_bait_enabled = bool(enabled_value)

        if auto_bait_enabled:
            bait_check_allowed = True
            bait_inventory_scan_exhausted = False
        else:
            bait_check_allowed = False
            bait_inventory_scan_exhausted = False


def get_auto_bait_enabled():
    with state_lock:
        return auto_bait_enabled


BAIT_TRIGGER_FISH = {
    "cod_fish",
    "gold_fish",
    "snapper_fish",
    "tiger_fish",
    "trout_fish",
    "tuna_fish",
}


def _is_bait_trigger_fish(category):
    return category in BAIT_TRIGGER_FISH


def _notify_state_callback():
    with state_lock:
        callback = state_callback
        current_state = enabled

    if callback is None:
        return

    try:
        callback(current_state)
    except Exception as error:
        _safe_print(f"State callback error: {error}")


def _notify_exit_callback():
    with state_lock:
        callback = exit_callback

    if callback is None:
        return

    try:
        callback()
    except Exception as error:
        _safe_print(f"Exit callback error: {error}")


def is_key_down(vk_code):
    try:
        return windows_is_key_down(vk_code)
    except Exception:
        return False


def _release_bait_c_key():
    try:
        c_release = getattr(
            BaitManager,
            "c_up",
            None,
        )

        if c_release is None:
            return

        c_release()

    except Exception as error:
        _safe_print(
            f"BAIT SAFETY: failed to release "
            f"BaitManager C key: {error}"
        )


def failsafe_input_loop():
    last_escape = False
    last_right_bracket = False

    try:
        while not failsafe_stop_event.is_set():
            escape_down = is_key_down(VK_ESCAPE)

            if escape_down and not last_escape:
                _release_bait_c_key()
                emergency_exit()
                break

            last_escape = escape_down

            right_bracket_down = is_key_down(
                VK_RIGHT_BRACKET
            )

            if right_bracket_down and not last_right_bracket:
                _release_bait_c_key()
                stop()

            last_right_bracket = right_bracket_down

            failsafe_stop_event.wait(0.01)

    except Exception as error:
        _safe_print(
            f"ERROR IN WINDOWS INPUT WATCHER: {error}"
        )


def start_failsafe():
    global failsafe_thread

    with state_lock:
        if (
            failsafe_thread is not None
            and failsafe_thread.is_alive()
        ):
            return

        failsafe_stop_event.clear()

        failsafe_thread = threading.Thread(
            target=failsafe_input_loop,
            name="WindowsInputWatcher",
            daemon=True,
        )

        failsafe_thread.start()


def stop_failsafe():
    failsafe_stop_event.set()

    with state_lock:
        worker = failsafe_thread

    if (
        worker is not None
        and worker.is_alive()
        and worker is not threading.current_thread()
    ):
        worker.join(timeout=0.5)


def initialize(new_detector=None):
    global detector
    global shutdown_requested
    global values_loaded

    with state_lock:
        if enabled:
            return False

        shutdown_requested = False

        if new_detector is not None:
            detector = new_detector

        if detector is None:
            values_loaded = False
            return False

        if not getattr(
            detector,
            "models_loaded",
            False,
        ):
            values_loaded = False
            return False

        values_loaded = True

        return True


def _release_detector(det):
    if det is None:
        return

    try:
        det.unload_models()
    except Exception:
        pass

    try:
        del det
    except Exception:
        pass

    gc.collect()

    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    except Exception:
        pass


def load_values(wanted_fish, wanted_other):
    global detector
    global values_loaded
    global shutdown_requested

    wanted_fish = list(wanted_fish)
    wanted_other = list(wanted_other)

    with state_lock:
        if enabled:
            return False

        if (
            fishing_thread is not None
            and fishing_thread.is_alive()
        ):
            return False

        shutdown_requested = False

    new_detector = None

    try:
        new_detector = FishDetector()

        new_detector.load_values(
            wanted_fish,
            wanted_other,
        )

        if not getattr(
            new_detector,
            "models_loaded",
            False,
        ):
            raise RuntimeError(
                "Models did not finish loading."
            )

        with state_lock:
            if enabled:
                _release_detector(new_detector)
                return False

            old_detector = detector
            detector = new_detector
            values_loaded = True

        _release_detector(old_detector)

        return True

    except Exception as error:
        values_loaded = False

        _safe_print(
            f"ERROR WHILE LOADING MODELS: "
            f"{type(error).__name__}: {error}"
        )

        _release_detector(new_detector)

        return False


def _send_mouse_input(flags, mouse_data=0):
    send_mouse_input(
        flags,
        mouse_data,
    )


def _send_scan_code(scan, key_up=False):
    send_scan_code(
        scan,
        key_up,
    )


def press_e():
    try:
        _send_scan_code(SCAN_E)

        time.sleep(0.15)

        _send_scan_code(
            SCAN_E,
            key_up=True,
        )

    except Exception as error:
        _safe_print(f"E key error: {error}")


def press_r():
    try:
        _send_scan_code(SCAN_R)

        time.sleep(0.15)

        _send_scan_code(
            SCAN_R,
            key_up=True,
        )

    except Exception as error:
        _safe_print(f"R key error: {error}")


def _left_click():
    _send_mouse_input(
        MOUSEEVENTF_LEFTDOWN
    )

    time.sleep(0.03)

    _send_mouse_input(
        MOUSEEVENTF_LEFTUP
    )


def _right_down():
    global right_mouse_held

    if right_mouse_held:
        return

    _send_mouse_input(
        MOUSEEVENTF_RIGHTDOWN
    )

    right_mouse_held = True


def _right_up():
    global right_mouse_held

    try:
        _send_mouse_input(
            MOUSEEVENTF_RIGHTUP
        )
    except Exception:
        pass

    right_mouse_held = False


def release_all_mouse():
    global right_mouse_held

    for release in (
        _right_up,
        lambda: _send_mouse_input(
            MOUSEEVENTF_LEFTUP
        ),
    ):
        try:
            release()
        except Exception:
            pass

    for button in (
        "left",
        "right",
        "middle",
    ):
        try:
            pyautogui.mouseUp(
                button=button
            )
        except Exception:
            pass

    _release_bait_c_key()

    right_mouse_held = False


def wait_for_buoy(continue_check):
    return wait_for_buoy_original(
        continue_check
    )


def _set_bait_check_allowed(value):
    global bait_check_allowed

    with state_lock:
        bait_check_allowed = bool(value)


def _get_bait_check_allowed():
    with state_lock:
        return bait_check_allowed


def _set_bait_inventory_scan_exhausted(value):
    global bait_inventory_scan_exhausted

    with state_lock:
        bait_inventory_scan_exhausted = bool(value)


def _get_bait_inventory_scan_exhausted():
    with state_lock:
        return bait_inventory_scan_exhausted


def _reset_bait_inventory_scan():
    _set_bait_inventory_scan_exhausted(False)
    _set_bait_check_allowed(True)


def _mark_bait_search_result():
    search_completed_without_match = getattr(
        BaitManager,
        "did_last_bait_search_complete_without_match",
        lambda: False,
    )()

    if search_completed_without_match:
        _set_bait_inventory_scan_exhausted(True)
        _set_bait_check_allowed(False)
    else:
        _set_bait_inventory_scan_exhausted(False)
        _set_bait_check_allowed(True)


def _run_bait_check(
    fishing_position,
    force_scan=False,
):
    if not get_auto_bait_enabled():
        return False

    if (
        not force_scan
        and not _get_bait_check_allowed()
    ):
        return False

    if not _should_continue():
        return False

    try:
        result = BaitManager.equip_bait_if_available(
            _should_continue,
            fishing_position,
        )

        _mark_bait_search_result()

        return result

    except Exception as error:
        _safe_print(
            "Bait check failed: "
            f"{type(error).__name__}: {error}"
        )

        _release_bait_c_key()

        try:
            pyautogui.moveTo(
                fishing_position[0],
                fishing_position[1],
                duration=0.1,
            )
        except Exception:
            pass

        return False


def pickup_and_check_inventory(
    check_bait=False,
):
    press_e()

    if not _should_continue():
        return False

    time.sleep(0.35)

    if not _should_continue():
        return False

    try:
        inventory_full = detect_inventory_full()

        if inventory_full:
            inventory_full_alert()
            stop()
            return True

    except Exception as error:
        _safe_print(
            "Inventory detection error: "
            f"{type(error).__name__}: {error}"
        )

    fishing_position = (
        int(pyautogui.position().x),
        int(pyautogui.position().y),
    )

    if (
        check_bait
        and get_auto_bait_enabled()
        and _get_bait_check_allowed()
        and _should_continue()
    ):
        _run_bait_check(
            fishing_position
        )

    return False


def unknown_item_alert(
    category,
    confidence,
):
    try:
        winsound.Beep(
            UNKNOWN_DING_FREQUENCY,
            UNKNOWN_DING_DURATION,
        )

    except Exception as error:
        _safe_print(
            f"Could not play ding: {error}"
        )


def inventory_full_alert():
    try:
        winsound.Beep(
            INVENTORY_FULL_FREQUENCY,
            INVENTORY_FULL_DURATION,
        )

    except Exception as error:
        _safe_print(
            f"Could not play inventory alert: {error}"
        )


def _should_continue():
    with state_lock:
        return (
            enabled
            and not shutdown_requested
            and not stop_event.is_set()
        )


def _equip_initial_bait_if_enabled(
    fishing_position,
):
    if not get_auto_bait_enabled():
        return

    if not _should_continue():
        return

    _reset_bait_inventory_scan()

    _run_bait_check(
        fishing_position,
        force_scan=True,
    )


def _run_stall_recovery(
    fishing_position,
    action_delay,
):
    if not _should_continue():
        return False

    _safe_print(
        "FISHING WATCHDOG: no new buoy or fish "
        f"detected for {FISHING_STALL_TIMEOUT:.0f} seconds. "
        "Resetting with E then R."
    )

    try:
        press_e()

        if not _should_continue():
            return False

        press_r()

        if not _should_continue():
            return False

        if stop_event.wait(
            max(0.0, float(action_delay))
        ):
            return False

        if not _should_continue():
            return False

        pyautogui.moveTo(
            fishing_position[0],
            fishing_position[1],
            duration=0.1,
        )

        time.sleep(0.05)

        if not _should_continue():
            return False

        _left_click()

        _safe_print(
            "FISHING WATCHDOG: fishing process restarted."
        )

        return True

    except Exception as error:
        _safe_print(
            "FISHING WATCHDOG recovery error: "
            f"{type(error).__name__}: {error}"
        )

        return False


def _wait_for_buoy_with_watchdog(
    continue_check,
):
    started_at = time.monotonic()
    timed_out = False

    def watchdog_continue_check():
        nonlocal timed_out

        if not continue_check():
            return False

        if (
            time.monotonic() - started_at
            >= FISHING_STALL_TIMEOUT
        ):
            timed_out = True
            return False

        return True

    result = wait_for_buoy(
        watchdog_continue_check
    )

    if timed_out:
        return None

    return result


def _detect_catch_with_watchdog(
    current_detector,
):
    started_at = time.monotonic()
    timed_out = False

    def watchdog_should_continue():
        nonlocal timed_out

        if not _should_continue():
            return False

        if (
            time.monotonic() - started_at
            >= FISHING_STALL_TIMEOUT
        ):
            timed_out = True
            return False

        return True

    result = current_detector.detect_catch(
        should_continue=watchdog_should_continue
    )

    if timed_out:
        return None

    return result


def fishing_loop(action_delay):
    global fishing_thread
    global enabled

    current_thread = threading.current_thread()

    try:
        _right_down()

        fishing_position = (
            int(pyautogui.position().x),
            int(pyautogui.position().y),
        )

        _equip_initial_bait_if_enabled(
            fishing_position
        )

        if not _should_continue():
            return

        pyautogui.moveTo(
            fishing_position[0],
            fishing_position[1],
            duration=0.1,
        )

        time.sleep(0.05)

        if not _should_continue():
            return

        _left_click()

        while _should_continue():
            with state_lock:
                current_detector = detector

                ready = (
                    values_loaded
                    and getattr(
                        current_detector,
                        "models_loaded",
                        False,
                    )
                )

            if not ready:
                stop()
                break

            buoy_state = _wait_for_buoy_with_watchdog(
                _should_continue
            )

            if not _should_continue():
                break

            if buoy_state is None:
                if not _run_stall_recovery(
                    fishing_position,
                    action_delay,
                ):
                    break

                continue

            if buoy_state == "missed":
                try:
                    press_r()

                except Exception as error:
                    _safe_print(
                        f"Line reset failed: {error}"
                    )

                    break

                if not _should_continue():
                    break

                if stop_event.wait(
                    action_delay
                ):
                    break

                if not _should_continue():
                    break

                try:
                    pyautogui.moveTo(
                        fishing_position[0],
                        fishing_position[1],
                        duration=0.1,
                    )

                    _left_click()

                except Exception as error:
                    _safe_print(
                        f"Re-cast failed: {error}"
                    )

                    break

                continue

            if buoy_state != "green":
                continue

            try:
                _left_click()

            except Exception as error:
                _safe_print(
                    f"Reel-in click failed: {error}"
                )

                continue

            if not _should_continue():
                break

            catch_result = _detect_catch_with_watchdog(
                current_detector
            )

            if catch_result is None:
                if not _run_stall_recovery(
                    fishing_position,
                    action_delay,
                ):
                    break

                continue

            category, confidence, wanted = (
                catch_result
            )

            if category == "cancelled":
                break

            if not _should_continue():
                break

            _safe_print(
                f"CATCH: {category} "
                f"({confidence:.1f}%)"
            )

            if category in {
                "unknown_fish",
                "unknown_other",
                "unknown",
            }:
                unknown_item_alert(
                    category,
                    confidence,
                )

                if pickup_and_check_inventory(
                    False
                ):
                    break

            elif category in {
                "no_fish",
                "no_bite",
            }:
                press_r()

            elif category == "broken_line":
                press_r()

            elif not _should_continue():
                break

            elif (
                get_auto_bait_enabled()
                and _get_bait_check_allowed()
                and _should_continue()
            ):
                _run_bait_check(
                    fishing_position
                )

            elif not wanted:
                _safe_print(
                    f"IGNORED: {category} "
                    f"({confidence:.1f}%) - not selected"
                )

                press_r()

                if not _should_continue():
                    break

                if (
                    get_auto_bait_enabled()
                    and _get_bait_check_allowed()
                    and _should_continue()
                ):
                    _run_bait_check(
                        fishing_position
                    )

            else:
                check_bait = (
                    _is_bait_trigger_fish(
                        category
                    )
                )

                if check_bait:
                    _reset_bait_inventory_scan()

                if pickup_and_check_inventory(
                    check_bait
                ):
                    break

                if not _should_continue():
                    break

                if (
                    not check_bait
                    and get_auto_bait_enabled()
                    and _get_bait_check_allowed()
                    and _should_continue()
                ):
                    _run_bait_check(
                        fishing_position
                    )

            if not _should_continue():
                break

            if stop_event.wait(
                action_delay
            ):
                break

            if not _should_continue():
                break

            try:
                pyautogui.moveTo(
                    fishing_position[0],
                    fishing_position[1],
                    duration=0.1,
                )

                time.sleep(0.05)

                _left_click()

            except Exception as error:
                _safe_print(
                    f"Re-cast failed: {error}"
                )

                break

    except Exception as error:
        _safe_print(
            "ERROR IN FISHING LOOP: "
            f"{type(error).__name__}: {error}"
        )

        stop()

    finally:
        release_all_mouse()
        _release_bait_c_key()

        with state_lock:
            enabled = False

            if fishing_thread is current_thread:
                fishing_thread = None

        _notify_state_callback()


def start_fishing_worker(action_delay):
    global fishing_thread
    global enabled

    try:
        action_delay = max(
            0.0,
            float(action_delay),
        )

    except (
        TypeError,
        ValueError,
    ):
        _safe_print("Invalid action delay.")
        return False

    with state_lock:
        if shutdown_requested:
            return False

        current_detector = detector

        if (
            current_detector is None
            or not values_loaded
            or not getattr(
                current_detector,
                "models_loaded",
                False,
            )
        ):
            return False

        if (
            fishing_thread is not None
            and fishing_thread.is_alive()
        ):
            return False

        if enabled:
            return False

        stop_event.clear()

        _set_bait_check_allowed(
            get_auto_bait_enabled()
        )

        _set_bait_inventory_scan_exhausted(
            False
        )

        enabled = True

        worker = threading.Thread(
            target=fishing_loop,
            args=(action_delay,),
            name="FishingWorker",
            daemon=True,
        )

        fishing_thread = worker

        try:
            worker.start()

        except Exception as error:
            _safe_print(
                "ERROR WHILE STARTING FISHING: "
                f"{type(error).__name__}: {error}"
            )

            with state_lock:
                enabled = False
                stop_event.set()

                if fishing_thread is worker:
                    fishing_thread = None

            release_all_mouse()
            _notify_state_callback()

            return False

    _notify_state_callback()

    return True


def is_worker_running():
    with state_lock:
        return (
            fishing_thread is not None
            and fishing_thread.is_alive()
        )


def stop():
    global enabled

    with state_lock:
        was_active = enabled

        enabled = False
        stop_event.set()

        _release_bait_c_key()
        release_all_mouse()

    if was_active:
        _notify_state_callback()

    return was_active


def emergency_exit():
    global shutdown_requested
    global enabled

    with state_lock:
        if shutdown_requested:
            return

        shutdown_requested = True
        enabled = False
        stop_event.set()

        _release_bait_c_key()
        release_all_mouse()

    stop_failsafe()
    _notify_state_callback()
    _notify_exit_callback()


def install_hotkeys():
    start_failsafe()
    return True


def uninstall_hotkeys():
    stop_failsafe()


def cleanup():
    global enabled
    global shutdown_requested
    global fishing_thread

    with state_lock:
        shutdown_requested = True
        enabled = False
        stop_event.set()

        worker = fishing_thread

        _release_bait_c_key()
        release_all_mouse()

    uninstall_hotkeys()

    if (
        worker is not None
        and worker.is_alive()
        and worker is not threading.current_thread()
    ):
        worker.join(timeout=2.0)

    _release_bait_c_key()
    release_all_mouse()

    with state_lock:
        enabled = False

        if (
            fishing_thread is worker
            and (
                worker is None
                or not worker.is_alive()
            )
        ):
            fishing_thread = None


if __name__ == "__main__":
    install_hotkeys()

    try:
        while not shutdown_requested:
            time.sleep(0.1)

    except KeyboardInterrupt:
        pass

    finally:
        cleanup()