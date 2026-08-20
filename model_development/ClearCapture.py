from pathlib import Path

# Root directory
captures = Path("../captures")

# Direct subfolders to clear
folders = [
    captures / "guns",
    captures / "junk",
    captures / "misc_bad",
    captures / "misc_good",
    captures / "no_fish",
    captures / "plastic",
    captures / "wood_chip",
]

# Also clear every fish-type folder inside captures/fish/
fish_folder = captures / "fish"
if fish_folder.exists():
    folders.extend(folder for folder in fish_folder.iterdir() if folder.is_dir())

# Image extensions to delete
image_extensions = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".webp",
    ".tif",
    ".tiff",
}

deleted = 0

for folder in folders:
    if not folder.exists():
        continue

    for file in folder.rglob("*"):
        if file.is_file() and file.suffix.lower() in image_extensions:
            file.unlink()
            deleted += 1
            print(f"Deleted: {file}")

print(f"\nDone. Deleted {deleted} images.")