from pathlib import Path
import sys


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

ASSETS_DIR = (
    BASE_DIR / "assets"
)

ICON_FILE = (
    ASSETS_DIR / "FishingDet.ico"
)

CONFIGURATION_DIR = (
    BASE_DIR / "configuration"
)

MODELS_DIR = (
    CONFIGURATION_DIR / "models"
)

CONFIG_IMAGES_DIR = (
    CONFIGURATION_DIR / "config_images"
)

BAIT_IMAGES_DIR = (
    CONFIGURATION_DIR / "bait_images"
)

SETTINGS_DIR = (
    CONFIGURATION_DIR / "settings"
)