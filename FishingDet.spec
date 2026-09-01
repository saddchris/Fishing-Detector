from pathlib import Path
import shutil


PROJECT_DIR = Path.cwd()

DIST_DIR = (
    PROJECT_DIR
    / "dist"
    / "FishingDet"
)

DIST_CONFIGURATION_DIR = (
    DIST_DIR
    / "configuration"
)

DIST_ASSETS_DIR = (
    DIST_DIR
    / "assets"
)


a = Analysis(
    [
        str(PROJECT_DIR / "GUIController.py"),
    ],
    pathex=[
        str(PROJECT_DIR),
    ],
    binaries=[],
    datas=[],
    hiddenimports=[
        "Main",
        "Detection",
        "BaitManager",
        "BuoyDetector",
        "TextDetection",
        "WindowsInput",
        "onnx",
        "onnxruntime",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torch.*",
        "torchvision",
        "torchvision.*",
        "torchaudio",
        "torchaudio.*",
    ],
    noarchive=False,
)


pyz = PYZ(
    a.pure,
)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FishingDet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(
        PROJECT_DIR
        / "assets"
        / "FishingDet.ico"
    ),
)


coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="FishingDet",
)


SOURCE_CONFIGURATION_DIR = (
    PROJECT_DIR
    / "configuration"
)

if SOURCE_CONFIGURATION_DIR.exists():

    if DIST_CONFIGURATION_DIR.exists():
        shutil.rmtree(
            DIST_CONFIGURATION_DIR
        )

    shutil.copytree(
        SOURCE_CONFIGURATION_DIR,
        DIST_CONFIGURATION_DIR,
        ignore=shutil.ignore_patterns(
            "*.pth"
        ),
    )

else:

    raise FileNotFoundError(
        "Could not find the configuration folder: "
        f"{SOURCE_CONFIGURATION_DIR}"
    )


SOURCE_ASSETS_DIR = (
    PROJECT_DIR
    / "assets"
)

if SOURCE_ASSETS_DIR.exists():

    if DIST_ASSETS_DIR.exists():
        shutil.rmtree(
            DIST_ASSETS_DIR
        )

    shutil.copytree(
        SOURCE_ASSETS_DIR,
        DIST_ASSETS_DIR,
    )

else:

    raise FileNotFoundError(
        "Could not find the assets folder: "
        f"{SOURCE_ASSETS_DIR}"
    )
