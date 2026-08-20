from pathlib import Path
import time
import pyautogui

# =========================
# SETTINGS
# =========================

CAPTURES = Path("../captures")

# Total number wanted for each class
FISH_IMAGES = 100

OBJECT_TARGETS = {
    "guns": 300,
    "junk": 200,
    "misc_bad": 200,
    "misc_good": 200,
    "no_fish": 300,
    "plastic": 200,
    "wood_chip": 200,
}

# Maximum screenshots taken each time you press ]
BATCH_SIZE = 100

# Time between screenshots
DELAY = 0.15


# =========================
# FIND CLASSES
# =========================

classes = []

# Fish types
fish_folder = CAPTURES / "fish"

if fish_folder.exists():
    for folder in sorted(fish_folder.iterdir()):
        if folder.is_dir():
            classes.append(folder)

# Object types
object_names = [
    "guns",
    "junk",
    "misc_bad",
    "misc_good",
    "no_fish",
    "plastic",
    "wood_chip",
]

for name in object_names:
    classes.append(CAPTURES / name)

# Make sure folders exist
for folder in classes:
    folder.mkdir(parents=True, exist_ok=True)


# =========================
# TARGET AMOUNT
# =========================

def get_target(folder):
    """Get the total target for this folder."""

    folder_name = folder.name

    if folder_name in OBJECT_TARGETS:
        return OBJECT_TARGETS[folder_name]

    # Fish types
    return FISH_IMAGES


# =========================
# COUNT IMAGES
# =========================

def count_images(folder):
    """Count PNG images in a folder."""

    return len(list(folder.glob("*.png")))


# =========================
# NEXT FILE NUMBER
# =========================

def get_next_number(folder):
    """Find the next numeric PNG filename."""

    numbers = []

    for file in folder.glob("*.png"):
        try:
            numbers.append(int(file.stem))
        except ValueError:
            pass

    return max(numbers, default=0) + 1


# =========================
# FIND NEXT INCOMPLETE
# =========================

def find_next_incomplete():
    """
    Find the first class that has not
    reached its total target.
    """

    for folder in classes:

        count = count_images(folder)
        target = get_target(folder)

        if count < target:
            return folder

    return None


# =========================
# TAKE BATCH
# =========================

def take_batch(folder):

    name = folder.relative_to(CAPTURES)

    existing_images = count_images(folder)
    target = get_target(folder)

    remaining = target - existing_images

    # Only take up to 100 at a time
    batch_amount = min(BATCH_SIZE, remaining)

    start_number = get_next_number(folder)

    print("\n================================")
    print(f"CLASS: {name}")
    print(f"TOTAL PROGRESS: {existing_images}/{target}")
    print(f"THIS BATCH: {batch_amount}")
    print(f"AFTER BATCH: {existing_images + batch_amount}/{target}")
    print("================================")

    # =========================
    # 5 SECOND COUNTDOWN
    # =========================

    print("GET READY!")

    for countdown in range(5, 0, -1):

        print(
            f"\rStarting in {countdown}...",
            end="",
            flush=True
        )

        time.sleep(1)

    print("\rSTARTING NOW!       ")

    print(f"Taking {batch_amount} screenshots...")

    # =========================
    # SCREENSHOTS
    # =========================

    for i in range(batch_amount):

        number = start_number + i

        filename = folder / f"{number:04d}.png"

        screenshot = pyautogui.screenshot()
        screenshot.save(filename)

        total_now = existing_images + i + 1

        print(
            f"\r{name}: {total_now}/{target}",
            end="",
            flush=True
        )

        time.sleep(DELAY)

    print("\n")

    # =========================
    # BATCH FINISHED
    # =========================

    new_total = count_images(folder)

    print("================================")
    print(f"BATCH FINISHED: {name}")
    print(f"TOTAL: {new_total}/{target}")
    print("================================")

    if new_total >= target:

        print(f"{name} IS COMPLETE!")

        # Tell them the next class
        next_folder = find_next_incomplete()

        if next_folder:

            next_count = count_images(next_folder)
            next_target = get_target(next_folder)

            print()
            print(f"NEXT CLASS: {next_folder.relative_to(CAPTURES)}")
            print(f"PROGRESS: {next_count}/{next_target}")

        else:

            print()
            print("ALL CLASSES ARE COMPLETE!")

    else:

        print()
        print(
            f"{name} still needs "
            f"{target - new_total} images."
        )

        print(
            "Switch to the next variation/object "
            "and press ] again."
        )


# =========================
# SHOW PROGRESS
# =========================

print("==========================================")
print("SCREENSHOT DATASET CAPTURE")
print("==========================================")
print()
print(f"Maximum per batch: {BATCH_SIZE}")
print()

print("Current progress:")

for folder in classes:

    count = count_images(folder)
    target = get_target(folder)

    status = "DONE" if count >= target else "INCOMPLETE"

    print(
        f"  {folder.relative_to(CAPTURES)}: "
        f"{count}/{target} [{status}]"
    )

print()
print("==========================================")


# =========================
# MAIN LOOP
# =========================

while True:

    # Find first incomplete class
    current_folder = find_next_incomplete()

    # Everything is finished
    if current_folder is None:

        print("\n================================")
        print("ALL CLASSES HAVE REACHED THEIR TARGET!")
        print("================================")

        break

    current_count = count_images(current_folder)
    current_target = get_target(current_folder)

    remaining = current_target - current_count

    batch_amount = min(BATCH_SIZE, remaining)

    print()
    print("------------------------------------------")
    print(
        f"NEXT: {current_folder.relative_to(CAPTURES)}"
    )
    print(
        f"TOTAL PROGRESS: "
        f"{current_count}/{current_target}"
    )
    print(
        f"NEXT BATCH: "
        f"{batch_amount} images"
    )
    print("Press ] + Enter when ready.")
    print("------------------------------------------")

    key = input()

    if key.strip() == "]":

        take_batch(current_folder)

    else:

        print("Please press ] and Enter.")