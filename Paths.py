from pathlib import Path

# Folder containing the application files.
BASE_DIR = Path(__file__).resolve().parent

# External configuration folder.
CONFIGURATION_DIR = (
    BASE_DIR / "configuration"
)

# Configuration subfolders.
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