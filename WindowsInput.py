import ctypes


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


ULONG_PTR = (
    ctypes.c_ulonglong
    if ctypes.sizeof(ctypes.c_void_p) == 8
    else ctypes.c_ulong
)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)

    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_UNION),
    ]

user32 = ctypes.windll.user32


_SEND_INPUT = user32.SendInput

_SEND_INPUT.argtypes = (
    ctypes.c_uint,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
)

_SEND_INPUT.restype = ctypes.c_uint


_GET_ASYNC_KEY_STATE = user32.GetAsyncKeyState

_GET_ASYNC_KEY_STATE.argtypes = (
    ctypes.c_int,
)

_GET_ASYNC_KEY_STATE.restype = ctypes.c_short

def send_input(event):
    sent = _SEND_INPUT(
        1,
        ctypes.byref(event),
        ctypes.sizeof(INPUT),
    )

    if sent != 1:
        raise ctypes.WinError()

def send_scan_code(scan, key_up=False):
    flags = KEYEVENTF_SCANCODE

    if key_up:
        flags |= KEYEVENTF_KEYUP

    event = INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(
            wVk=0,
            wScan=scan,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        ),
    )

    send_input(event)

def send_mouse_input(flags, mouse_data=0):
    event = INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(
            dx=0,
            dy=0,
            mouseData=mouse_data,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        ),
    )

    send_input(event)


def send_left_mouse_down():
    send_mouse_input(
        MOUSEEVENTF_LEFTDOWN
    )


def send_left_mouse_up():
    send_mouse_input(
        MOUSEEVENTF_LEFTUP
    )


def send_right_mouse_down():
    send_mouse_input(
        MOUSEEVENTF_RIGHTDOWN
    )


def send_right_mouse_up():
    send_mouse_input(
        MOUSEEVENTF_RIGHTUP
    )


def send_left_click():
    send_left_mouse_down()
    send_left_mouse_up()


def send_right_click():
    send_right_mouse_down()
    send_right_mouse_up()

def is_key_down(vk_code):
    return bool(
        _GET_ASYNC_KEY_STATE(vk_code) & 0x8000
    )