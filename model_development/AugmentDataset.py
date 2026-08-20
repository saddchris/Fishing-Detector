from pathlib import Path
import random
import shutil
from PIL import Image

MASTER_DIR = Path("../captures")

TRAIN_DIR = Path("../training_captures")
VALIDATION_DIR = Path("../validation_captures")
TEST_DIR = Path("../test_captures")

MASK_FILE = Path("../configuration/config_images/FishingRod_Mask.png")

TRAIN_PERCENTAGE = 0.70
VALIDATION_PERCENTAGE = 0.15
TEST_PERCENTAGE = 0.15

ROTATIONS = [
    -20,
    -10,
    10,
    20
]

RANDOM_SEED = 42

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
}

DIRECT_CLASSES = [
    "guns",
    "misc_good",
    "misc_bad",
    "no_fish",
    "plastic",
    "wood_chip",
    "junk"
]

if not MASTER_DIR.exists():

    raise FileNotFoundError(
        f"Master captures directory does not exist:\n"
        f"{MASTER_DIR}"
    )

if not MASK_FILE.exists():

    raise FileNotFoundError(
        f"Fishing rod mask does not exist:\n"
        f"{MASK_FILE}"
    )

total_percentage = (
    TRAIN_PERCENTAGE
    + VALIDATION_PERCENTAGE
    + TEST_PERCENTAGE
)

if abs(total_percentage - 1.0) > 0.0001:

    raise ValueError(
        "TRAIN_PERCENTAGE + "
        "VALIDATION_PERCENTAGE + "
        "TEST_PERCENTAGE "
        "must equal 1.0"
    )

print("=" * 70)
print("CREATING TRAINING / VALIDATION / TEST DATASET")
print("=" * 70)

print("\nMaster database:")
print(f"  {MASTER_DIR}")

print("\nMask:")
print(f"  {MASK_FILE}")

print("\nTraining output:")
print(f"  {TRAIN_DIR}")

print("\nValidation output:")
print(f"  {VALIDATION_DIR}")

print("\nTest output:")
print(f"  {TEST_DIR}")

mask_source = Image.open(
    MASK_FILE
).convert("RGBA")

print(
    f"\nMask size: "
    f"{mask_source.width}x{mask_source.height}"
)

print("\n" + "=" * 70)
print("REMOVING OLD GENERATED DATASETS")
print("=" * 70)

if TRAIN_DIR.exists():

    print(
        f"\nRemoving existing "
        f"{TRAIN_DIR}..."
    )

    shutil.rmtree(TRAIN_DIR)

if VALIDATION_DIR.exists():

    print(
        f"\nRemoving existing "
        f"{VALIDATION_DIR}..."
    )

    shutil.rmtree(VALIDATION_DIR)

if TEST_DIR.exists():

    print(
        f"\nRemoving existing "
        f"{TEST_DIR}..."
    )

    shutil.rmtree(TEST_DIR)

TRAIN_DIR.mkdir(
    parents=True,
    exist_ok=True
)

VALIDATION_DIR.mkdir(
    parents=True,
    exist_ok=True
)

TEST_DIR.mkdir(
    parents=True,
    exist_ok=True
)

random.seed(
    RANDOM_SEED
)


def get_images(source_dir):

    if not source_dir.exists():

        return []

    images = [
        image
        for image in source_dir.iterdir()
        if (
            image.is_file()
            and image.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    ]

    images.sort(
        key=lambda x: x.name.lower()
    )

    return images


def prepare_mask_for_image(image):

    image_width, image_height = image.size

    image_aspect = (
        image_width
        / image_height
    )

    mask_width, mask_height = mask_source.size

    mask_aspect = (
        mask_width
        / mask_height
    )

    if mask_aspect > image_aspect:

        crop_width = int(
            mask_height
            * image_aspect
        )

        left = (
            mask_width
            - crop_width
        ) // 2

        mask = mask_source.crop(
            (
                left,
                0,
                left + crop_width,
                mask_height
            )
        )

    else:

        crop_height = int(
            mask_width
            / image_aspect
        )

        top = (
            mask_height
            - crop_height
        ) // 2

        mask = mask_source.crop(
            (
                0,
                top,
                mask_width,
                top + crop_height
            )
        )

    mask = mask.resize(
        (
            image_width,
            image_height
        ),
        Image.Resampling.LANCZOS
    )

    return mask


def apply_rod_mask(image):

    image = image.convert(
        "RGBA"
    )

    mask = prepare_mask_for_image(
        image
    )

    result = Image.alpha_composite(
        image,
        mask
    )

    return result.convert(
        "RGB"
    )


def save_masked_image(
    source_path,
    output_path
):

    try:

        image = Image.open(
            source_path
        ).convert("RGB")

    except Exception as error:

        print(
            "\nWARNING: Could not open:"
        )

        print(
            f"  {source_path}"
        )

        print(
            f"  {error}"
        )

        return False

    try:

        masked = apply_rod_mask(
            image
        )

        masked.save(
            output_path
        )

        masked.close()
        image.close()

        return True

    except Exception as error:

        image.close()

        print(
            "\nWARNING: Could not apply mask:"
        )

        print(
            f"  {source_path}"
        )

        print(
            f"  {error}"
        )

        return False


def split_and_copy(
    source_dir,
    train_dir,
    validation_dir,
    test_dir
):

    images = get_images(
        source_dir
    )

    random.shuffle(
        images
    )

    total = len(images)

    test_count = int(
        total
        * TEST_PERCENTAGE
    )

    validation_count = int(
        total
        * VALIDATION_PERCENTAGE
    )

    train_count = (
        total
        - validation_count
        - test_count
    )

    train_images = images[
        :train_count
    ]

    validation_images = images[
        train_count:
        train_count + validation_count
    ]

    test_images = images[
        train_count + validation_count:
    ]

    train_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    validation_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    test_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    for image in train_images:

        save_masked_image(
            image,
            train_dir / image.name
        )

    for image in validation_images:

        save_masked_image(
            image,
            validation_dir / image.name
        )

    for image in test_images:

        save_masked_image(
            image,
            test_dir / image.name
        )

    return (
        total,
        len(train_images),
        len(validation_images),
        len(test_images)
    )


print("\n" + "=" * 70)
print("PROCESSING DIRECT CLASSES")
print("=" * 70)

total_originals = 0
total_training = 0
total_validation = 0
total_test = 0

for class_name in DIRECT_CLASSES:

    source_dir = (
        MASTER_DIR
        / class_name
    )

    if not source_dir.exists():

        print(
            f"\nWARNING: Folder not found:"
            f" {source_dir}"
        )

        continue

    train_dir = (
        TRAIN_DIR
        / class_name
    )

    validation_dir = (
        VALIDATION_DIR
        / class_name
    )

    test_dir = (
        TEST_DIR
        / class_name
    )

    (
        total,
        training,
        validation,
        test
    ) = split_and_copy(
        source_dir,
        train_dir,
        validation_dir,
        test_dir
    )

    total_originals += total
    total_training += training
    total_validation += validation
    total_test += test

    print(
        f"\n{class_name}"
    )

    print(
        "-" * 50
    )

    print(
        f"  Original:    {total}"
    )

    print(
        f"  Training:    {training}"
    )

    print(
        f"  Validation:  {validation}"
    )

    print(
        f"  Test:        {test}"
    )


print("\n" + "=" * 70)
print("PROCESSING FISH TYPES")
print("=" * 70)

FISH_DIR = (
    MASTER_DIR
    / "fish"
)

if not FISH_DIR.exists():

    print(
        "\nWARNING: "
        "captures/fish does not exist!"
    )

else:

    fish_types = [
        folder
        for folder in FISH_DIR.iterdir()
        if folder.is_dir()
    ]

    fish_types.sort(
        key=lambda x: x.name.lower()
    )

    print(
        f"\nFound "
        f"{len(fish_types)} fish types."
    )

    for fish_type_dir in fish_types:

        fish_type = (
            fish_type_dir.name
        )

        train_dir = (
            TRAIN_DIR
            / "fish"
            / fish_type
        )

        validation_dir = (
            VALIDATION_DIR
            / "fish"
            / fish_type
        )

        test_dir = (
            TEST_DIR
            / "fish"
            / fish_type
        )

        (
            total,
            training,
            validation,
            test
        ) = split_and_copy(
            fish_type_dir,
            train_dir,
            validation_dir,
            test_dir
        )

        total_originals += total
        total_training += training
        total_validation += validation
        total_test += test

        print(
            f"\nfish/{fish_type}"
        )

        print(
            "-" * 50
        )

        print(
            f"  Original:    {total}"
        )

        print(
            f"  Training:    {training}"
        )

        print(
            f"  Validation:  {validation}"
        )

        print(
            f"  Test:        {test}"
        )


print("\n" + "=" * 70)
print("CREATING ROTATED TRAINING IMAGES")
print("=" * 70)

total_rotated = 0


def augment_directory(directory):

    global total_rotated

    for path in directory.iterdir():

        if path.is_dir():

            augment_directory(
                path
            )

            continue

        if not path.is_file():

            continue

        if (
            path.suffix.lower()
            not in IMAGE_EXTENSIONS
        ):

            continue

        if "_rot" in path.stem:

            continue

        try:

            image = Image.open(
                path
            ).convert("RGB")

        except Exception as error:

            print(
                "\nWARNING: "
                "Could not open:"
            )

            print(
                f"  {path}"
            )

            print(
                f"  {error}"
            )

            continue

        for angle in ROTATIONS:

            output_name = (
                f"{path.stem}"
                f"_rot{angle}"
                f"{path.suffix.lower()}"
            )

            output_path = (
                path.parent
                / output_name
            )

            rotated = image.rotate(
                angle,
                resample=Image.Resampling.BICUBIC,
                expand=True
            )

            rotated.save(
                output_path
            )

            rotated.close()

            total_rotated += 1

        image.close()


augment_directory(
    TRAIN_DIR
)

mask_source.close()

print("\n" + "=" * 70)
print("DATASET CREATION COMPLETE")
print("=" * 70)

print("\nOriginal images:")
print(
    f"  Total:       {total_originals}"
)

print(
    f"  Training:    {total_training}"
)

print(
    f"  Validation:  {total_validation}"
)

print(
    f"  Test:        {total_test}"
)

print("\nAugmented images:")

print(
    f"  Rotated training images: "
    f"{total_rotated}"
)

print("\nFinal dataset:")

print(
    f"  {TRAIN_DIR}"
)

print(
    f"  {VALIDATION_DIR}"
)

print(
    f"  {TEST_DIR}"
)

print("\nMask applied:")

print(
    f"  {MASK_FILE}"
)

print("\nIMPORTANT:")

print(
    "  Original captures were never modified."
)

print(
    "  The fishing rod mask was applied to "
    "training, validation, and test images."
)

print(
    "  Only training images were augmented."
)

print(
    "  Validation contains masked original images only."
)

print(
    "  Test contains masked original images only."
)

print("\nDone!")