import copy
import json
import random
import time
from pathlib import Path

import torch
from PIL import Image, ImageFile
from torch import nn, optim
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import models, transforms


TRAIN_DIR = Path("../training_captures")
VALIDATION_DIR = Path("../validation_captures")
TEST_DIR = Path("../test_captures")

TRAIN_STAGES = [2, 3]
NUM_TUNING_TRIALS = 4
MAX_EPOCHS = 30
EARLY_STOPPING_PATIENCE = 6

NUM_WORKERS = 2
PIN_MEMORY = True
PREFETCH_FACTOR = 2
PERSISTENT_WORKERS = False
USE_RAM_IMAGE_CACHE = False
BATCH_SIZE = 16
RANDOM_SEED = 42
GRADIENT_CLIP_VALUE = 1.0
DROPOUT_RATE = 0.2

MODEL_NAME = "resnet18"
TUNING_RESULTS_FILE = "tuning_results.json"
STAGE1_BEST_FILE = "../configuration/models/stage1_model.pth"
STAGE2_BEST_FILE = "../configuration/models/fish_model.pth"
STAGE3_BEST_FILE = "../configuration/models/other_model.pth"

ImageFile.LOAD_TRUNCATED_IMAGES = True
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_MIXED_PRECISION = torch.cuda.is_available()

if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

STAGE3_OTHER_CLASSES = [
    "guns",
    "misc_good",
    "misc_bad",
    "plastic",
    "wood_chip",
    "junk",
]

STAGE1_SEARCH_SPACE = {
    "image_size": [224, 320],
    "learning_rate": [0.00005, 0.0001, 0.0002, 0.0003],
    "weight_decay": [0.00001, 0.00005, 0.0001, 0.0003],
    "label_smoothing": [0.0, 0.03, 0.05, 0.1],
    "backbone_lr_multiplier": [0.05, 0.1, 0.2, 0.3],
    "head_only_epochs": [0, 2, 3],
    "scheduler": ["cosine", "plateau"],
}

STAGE2_SEARCH_SPACE = {
    "image_size": [224, 320],
    "learning_rate": [0.00003, 0.00005, 0.0001, 0.0002],
    "weight_decay": [0.00001, 0.00005, 0.0001, 0.0003],
    "label_smoothing": [0.0, 0.03, 0.05, 0.1],
    "backbone_lr_multiplier": [0.05, 0.1, 0.2],
    "head_only_epochs": [0, 2, 3],
    "scheduler": ["cosine", "plateau"],
}

STAGE3_SEARCH_SPACE = {
    "image_size": [224, 320],
    "learning_rate": [0.00005, 0.0001, 0.0002, 0.0003],
    "weight_decay": [0.00001, 0.00005, 0.0001, 0.0003],
    "label_smoothing": [0.0, 0.03, 0.05, 0.1],
    "backbone_lr_multiplier": [0.05, 0.1, 0.2, 0.3],
    "head_only_epochs": [0, 2, 3],
    "scheduler": ["cosine", "plateau"],
}

_IMAGE_CACHE = {}


def set_seed(seed):
    random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_cached_image(image_path):
    image_path = str(image_path)

    if USE_RAM_IMAGE_CACHE:
        cached = _IMAGE_CACHE.get(image_path)

        if cached is not None:
            return cached.copy()

    image = Image.open(image_path).convert("RGB")

    if USE_RAM_IMAGE_CACHE:
        _IMAGE_CACHE[image_path] = image.copy()

    return image


class ImageListDataset(Dataset):
    def __init__(self, samples, classes, transform=None):
        self.samples = samples
        self.classes = classes
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        image_path, label = self.samples[index]

        image = load_cached_image(image_path)

        if self.transform:
            image = self.transform(image)

        return image, label


def get_images(directory):
    if not directory.exists():
        return []

    return sorted(
        [
            path
            for path in directory.rglob("*")
            if (
                path.is_file()
                and path.suffix.lower() in IMAGE_EXTENSIONS
            )
        ],
        key=lambda x: str(x).lower(),
    )


def build_dataset(samples_by_class):
    classes = sorted(samples_by_class.keys())

    class_to_index = {
        name: index
        for index, name in enumerate(classes)
    }

    samples = []

    for class_name in classes:
        label = class_to_index[class_name]

        for image_path in samples_by_class[class_name]:
            samples.append((image_path, label))

    return samples, classes


def build_stage1_dataset(root):
    data = {
        "fish": [],
        "other": [],
        "no_fish": [],
    }

    fish_dir = root / "fish"

    if fish_dir.exists():
        data["fish"].extend(get_images(fish_dir))

    no_fish_dir = root / "no_fish"

    if no_fish_dir.exists():
        data["no_fish"].extend(get_images(no_fish_dir))

    for class_name in STAGE3_OTHER_CLASSES:
        class_dir = root / class_name

        if class_dir.exists():
            data["other"].extend(get_images(class_dir))

    data = {
        class_name: images
        for class_name, images in data.items()
        if images
    }

    return build_dataset(data)


def build_fish_dataset(root):
    data = {}

    fish_dir = root / "fish"

    if not fish_dir.exists():
        return [], []

    for fish_type in fish_dir.iterdir():

        if not fish_type.is_dir():
            continue

        images = get_images(fish_type)

        if images:
            data[fish_type.name] = images

    return build_dataset(data)


def build_other_dataset(root):
    data = {}

    for class_name in STAGE3_OTHER_CLASSES:

        class_dir = root / class_name

        images = get_images(class_dir)

        if images:
            data[class_name] = images

    return build_dataset(data)


def print_class_counts(samples, classes):
    counts = {class_name: 0 for class_name in classes}

    for _, label in samples:
        class_name = classes[label]
        counts[class_name] += 1

    for class_name in classes:
        print(f"  {class_name:25s}: {counts[class_name]:6d}")


def compute_class_counts(samples, classes):
    counts = {class_name: 0 for class_name in classes}

    for _, label in samples:
        counts[classes[label]] += 1

    return counts


def compute_class_weights(samples, classes):
    counts = compute_class_counts(samples, classes)
    total = sum(counts.values())

    weights = []

    for class_name in classes:
        count = counts[class_name]

        if count > 0:
            weights.append(total / (len(classes) * count))
        else:
            weights.append(0.0)

    return torch.tensor(weights, dtype=torch.float32)


def build_sample_weights(samples, classes):
    counts = compute_class_counts(samples, classes)

    weights = []

    for _, label in samples:
        class_name = classes[label]
        count = counts[class_name]

        weights.append(1.0 / count if count > 0 else 0.0)

    return torch.tensor(weights, dtype=torch.double)


def create_train_transform(image_size):
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(
                image_size,
                scale=(0.75, 1.0),
                ratio=(0.85, 1.15),
            ),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(10),
            transforms.ColorJitter(
                brightness=0.2,
                contrast=0.2,
                saturation=0.2,
                hue=0.03,
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=IMAGENET_MEAN,
                std=IMAGENET_STD,
            ),
        ]
    )


def create_validation_transform(image_size):
    return transforms.Compose(
        [
            transforms.Resize(image_size),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=IMAGENET_MEAN,
                std=IMAGENET_STD,
            ),
        ]
    )


def create_dataloader(dataset, shuffle, sampler=None):
    worker_count = max(0, NUM_WORKERS)

    kwargs = {
        "dataset": dataset,
        "batch_size": BATCH_SIZE,
        "num_workers": worker_count,
        "pin_memory": PIN_MEMORY and torch.cuda.is_available(),
        "drop_last": False,
    }

    if sampler is not None:
        kwargs["sampler"] = sampler
        kwargs["shuffle"] = False
    else:
        kwargs["shuffle"] = shuffle

    if worker_count > 0:
        kwargs["prefetch_factor"] = PREFETCH_FACTOR
        kwargs["persistent_workers"] = PERSISTENT_WORKERS

    return DataLoader(**kwargs)


def create_model(number_of_classes):
    if MODEL_NAME == "resnet18":
        model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

    elif MODEL_NAME == "resnet34":
        model = models.resnet34(weights=models.ResNet34_Weights.DEFAULT)

    else:
        raise ValueError(f"Unsupported model: {MODEL_NAME}")

    model.fc = nn.Sequential(
        nn.Dropout(p=DROPOUT_RATE),
        nn.Linear(model.fc.in_features, number_of_classes),
    )

    model = model.to(device)

    return model


def freeze_backbone(model):
    for parameter in model.parameters():
        parameter.requires_grad = False

    for parameter in model.fc.parameters():
        parameter.requires_grad = True


def unfreeze_backbone(model):
    for parameter in model.parameters():
        parameter.requires_grad = True


def create_optimizer(model, learning_rate, backbone_lr_multiplier, weight_decay):
    backbone_parameters = []
    head_parameters = []

    for name, parameter in model.named_parameters():

        if not parameter.requires_grad:
            continue

        if name.startswith("fc."):
            head_parameters.append(parameter)

        else:
            backbone_parameters.append(parameter)

    parameter_groups = []

    if backbone_parameters:
        parameter_groups.append(
            {
                "params": backbone_parameters,
                "lr": learning_rate * backbone_lr_multiplier,
            }
        )

    if head_parameters:
        parameter_groups.append(
            {
                "params": head_parameters,
                "lr": learning_rate,
            }
        )

    return optim.AdamW(parameter_groups, weight_decay=weight_decay)


def evaluate_model(model, data_loader, classes, criterion):
    model.eval()

    total = 0
    correct = 0
    total_loss = 0.0

    class_correct = {class_name: 0 for class_name in classes}
    class_total = {class_name: 0 for class_name in classes}

    with torch.inference_mode():

        for images, labels in data_loader:

            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            if USE_MIXED_PRECISION:

                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    outputs = model(images)
                    loss = criterion(outputs, labels)

            else:

                outputs = model(images)
                loss = criterion(outputs, labels)

            total_loss += loss.item() * labels.size(0)

            _, predicted = torch.max(outputs, 1)

            total += labels.size(0)
            correct += (predicted == labels).sum().item()

            for label, prediction in zip(labels, predicted):

                class_name = classes[label.item()]
                class_total[class_name] += 1

                if prediction.item() == label.item():
                    class_correct[class_name] += 1

    accuracy = 100 * correct / total if total > 0 else 0
    average_loss = total_loss / total if total > 0 else 0

    class_accuracy = {}

    for class_name in classes:

        if class_total[class_name] > 0:
            class_accuracy[class_name] = (
                100 * class_correct[class_name] / class_total[class_name]
            )
        else:
            class_accuracy[class_name] = 0

    valid_accuracies = [
        class_accuracy[class_name]
        for class_name in classes
        if class_total[class_name] > 0
    ]

    balanced_accuracy = (
        sum(valid_accuracies) / len(valid_accuracies)
        if valid_accuracies
        else 0
    )

    return accuracy, average_loss, class_accuracy, balanced_accuracy


def sample_hyperparameters(search_space):
    return {name: random.choice(values) for name, values in search_space.items()}


def create_scheduler(optimizer, scheduler_type, remaining_epochs):
    if scheduler_type == "cosine":

        return optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=max(1, remaining_epochs),
            eta_min=1e-6,
        )

    if scheduler_type == "plateau":

        return optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="max",
            factor=0.3,
            patience=3,
            min_lr=1e-6,
        )

    raise ValueError(f"Unknown scheduler: {scheduler_type}")


def train_one_epoch(model, loader, criterion, optimizer, scaler):
    model.train()

    running_loss = 0.0
    total = 0
    correct = 0

    for images, labels in loader:

        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        if USE_MIXED_PRECISION:

            with torch.autocast(device_type="cuda", dtype=torch.float16):
                outputs = model(images)
                loss = criterion(outputs, labels)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)

            torch.nn.utils.clip_grad_norm_(
                model.parameters(), GRADIENT_CLIP_VALUE
            )

            scaler.step(optimizer)
            scaler.update()

        else:

            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                model.parameters(), GRADIENT_CLIP_VALUE
            )

            optimizer.step()

        running_loss += loss.item() * labels.size(0)

        _, predicted = torch.max(outputs, 1)

        total += labels.size(0)
        correct += (predicted == labels).sum().item()

    average_loss = running_loss / total if total > 0 else 0
    accuracy = 100 * correct / total if total > 0 else 0

    return average_loss, accuracy


def move_state_to_cpu(state):
    return {key: value.detach().cpu().clone() for key, value in state.items()}


def cleanup_model(model):
    if model is not None:
        model.cpu()

    del model

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass


def train_trial(
    stage_number,
    trial_number,
    hyperparameters,
    train_samples,
    train_classes,
    validation_samples,
    validation_classes,
):
    print(f"\n{'#' * 70}")
    print(f"STAGE {stage_number} - TRIAL {trial_number}")
    print(f"{'#' * 70}\n")

    print("Hyperparameters:")

    for name, value in hyperparameters.items():
        print(f"  {name}: {value}")

    start_time = time.time()

    image_size = hyperparameters["image_size"]
    learning_rate = hyperparameters["learning_rate"]
    weight_decay = hyperparameters["weight_decay"]
    label_smoothing = hyperparameters["label_smoothing"]
    backbone_lr_multiplier = hyperparameters["backbone_lr_multiplier"]
    head_only_epochs = hyperparameters["head_only_epochs"]
    scheduler_type = hyperparameters["scheduler"]

    train_dataset = ImageListDataset(
        train_samples,
        train_classes,
        transform=create_train_transform(image_size),
    )

    validation_dataset = ImageListDataset(
        validation_samples,
        validation_classes,
        transform=create_validation_transform(image_size),
    )

    sample_weights = build_sample_weights(train_samples, train_classes)

    train_sampler = WeightedRandomSampler(
        sample_weights,
        num_samples=len(sample_weights),
        replacement=True,
    )

    train_loader = create_dataloader(
        train_dataset, shuffle=False, sampler=train_sampler
    )

    validation_loader = create_dataloader(validation_dataset, shuffle=False)

    model = create_model(len(train_classes))

    class_weights = compute_class_weights(
        train_samples, train_classes
    ).to(device)

    criterion = nn.CrossEntropyLoss(
        weight=class_weights, label_smoothing=label_smoothing
    )

    eval_criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)

    scaler = torch.amp.GradScaler("cuda") if USE_MIXED_PRECISION else None

    if head_only_epochs > 0:

        print(f"\nHead-only phase: {head_only_epochs} epochs")

        freeze_backbone(model)

        optimizer = create_optimizer(
            model, learning_rate, backbone_lr_multiplier, weight_decay
        )

        head_scheduler = optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=max(1, head_only_epochs),
            eta_min=learning_rate * 0.1,
        )

        for epoch in range(head_only_epochs):

            train_loss, train_accuracy = train_one_epoch(
                model, train_loader, criterion, optimizer, scaler
            )

            head_scheduler.step()

            print(
                f"Head epoch {epoch + 1:2}/{head_only_epochs} | "
                f"Loss {train_loss:.4f} | Train {train_accuracy:5.1f}%"
            )

    print(f"\nUnfreezing entire {MODEL_NAME}...")

    unfreeze_backbone(model)

    optimizer = create_optimizer(
        model, learning_rate, backbone_lr_multiplier, weight_decay
    )

    remaining_epochs = max(1, MAX_EPOCHS - head_only_epochs)

    scheduler = create_scheduler(optimizer, scheduler_type, remaining_epochs)

    best_validation_accuracy = 0.0
    best_validation_balanced_accuracy = 0.0
    best_validation_loss = float("inf")
    best_epoch = 0
    epochs_without_improvement = 0
    best_state = None

    for epoch in range(remaining_epochs):

        actual_epoch = head_only_epochs + epoch + 1

        training_loss, training_accuracy = train_one_epoch(
            model, train_loader, criterion, optimizer, scaler
        )

        (
            validation_accuracy,
            validation_loss,
            _,
            validation_balanced_accuracy,
        ) = evaluate_model(
            model, validation_loader, validation_classes, eval_criterion
        )

        current_lr = optimizer.param_groups[0]["lr"]

        if scheduler_type == "plateau":
            scheduler.step(validation_balanced_accuracy)
        else:
            scheduler.step()

        improved = False

        if validation_balanced_accuracy > best_validation_balanced_accuracy:
            improved = True

        elif (
            validation_balanced_accuracy == best_validation_balanced_accuracy
            and validation_loss < best_validation_loss
        ):
            improved = True

        if improved:

            best_validation_accuracy = validation_accuracy
            best_validation_balanced_accuracy = validation_balanced_accuracy
            best_validation_loss = validation_loss
            best_epoch = actual_epoch
            epochs_without_improvement = 0
            best_state = move_state_to_cpu(model.state_dict())

            status = " <-- BEST"

        else:

            epochs_without_improvement += 1
            status = ""

        print(
            f"Epoch {actual_epoch:2}/{MAX_EPOCHS} | "
            f"LR {current_lr:.2e} | "
            f"Loss {training_loss:.4f} | "
            f"Train {training_accuracy:5.1f}% | "
            f"Val {validation_accuracy:5.1f}% | "
            f"Val Bal {validation_balanced_accuracy:5.1f}% | "
            f"Val Loss {validation_loss:.4f}"
            f"{status}"
        )

        if epochs_without_improvement >= EARLY_STOPPING_PATIENCE:

            print("\nEarly stopping.")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    elapsed = time.time() - start_time

    result = {
        "stage": stage_number,
        "trial": trial_number,
        "model_name": MODEL_NAME,
        "hyperparameters": hyperparameters,
        "best_validation_accuracy": best_validation_accuracy,
        "best_validation_balanced_accuracy": best_validation_balanced_accuracy,
        "best_validation_loss": best_validation_loss,
        "best_epoch": best_epoch,
        "training_time_seconds": round(elapsed, 2),
    }

    print(f"\n{'-' * 70}")
    print(f"TRIAL {trial_number} COMPLETE")
    print(f"{'-' * 70}")
    print(f"Best validation accuracy: {best_validation_accuracy:.2f}%")
    print(
        f"Best validation balanced accuracy: "
        f"{best_validation_balanced_accuracy:.2f}%"
    )
    print(f"Best validation loss: {best_validation_loss:.4f}")
    print(f"Best epoch: {best_epoch}")
    print(f"Training time: {elapsed / 60:.1f} minutes")

    return result, model


def test_best_model(model, test_samples, test_classes, image_size, label_smoothing):
    print(f"\n{'=' * 70}")
    print("FINAL TEST EVALUATION")
    print(f"{'=' * 70}")

    test_dataset = ImageListDataset(
        test_samples,
        test_classes,
        transform=create_validation_transform(image_size),
    )

    test_loader = create_dataloader(test_dataset, shuffle=False)

    model.eval()

    total = 0
    correct = 0
    total_loss = 0.0

    class_correct = {class_name: 0 for class_name in test_classes}
    class_total = {class_name: 0 for class_name in test_classes}

    with torch.inference_mode():

        for images, labels in test_loader:

            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            flipped_images = torch.flip(images, dims=[3])

            if USE_MIXED_PRECISION:

                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    outputs = model(images)
                    flipped_outputs = model(flipped_images)

            else:

                outputs = model(images)
                flipped_outputs = model(flipped_images)

            probabilities = (
                torch.softmax(outputs, dim=1)
                + torch.softmax(flipped_outputs, dim=1)
            ) / 2

            loss = nn.functional.nll_loss(
                torch.log(probabilities.clamp(min=1e-8)), labels
            )

            total_loss += loss.item() * labels.size(0)

            _, predicted = torch.max(probabilities, 1)

            total += labels.size(0)
            correct += (predicted == labels).sum().item()

            for label, prediction in zip(labels, predicted):

                class_name = test_classes[label.item()]
                class_total[class_name] += 1

                if prediction.item() == label.item():
                    class_correct[class_name] += 1

    test_accuracy = 100 * correct / total if total > 0 else 0
    test_loss = total_loss / total if total > 0 else 0

    class_accuracy = {}

    for class_name in test_classes:

        if class_total[class_name] > 0:
            class_accuracy[class_name] = (
                100 * class_correct[class_name] / class_total[class_name]
            )
        else:
            class_accuracy[class_name] = 0

    valid_accuracies = [
        class_accuracy[class_name]
        for class_name in test_classes
        if class_total[class_name] > 0
    ]

    balanced_test_accuracy = (
        sum(valid_accuracies) / len(valid_accuracies)
        if valid_accuracies
        else 0
    )

    print(f"\nFINAL TEST ACCURACY: {test_accuracy:.2f}%")
    print(f"FINAL TEST BALANCED ACCURACY: {balanced_test_accuracy:.2f}%")
    print(f"FINAL TEST LOSS: {test_loss:.4f}")
    print("\nPer-class test accuracy:")

    for class_name in test_classes:
        print(f"  {class_name:25s}: {class_accuracy[class_name]:5.1f}%")

    return test_accuracy, test_loss, class_accuracy, balanced_test_accuracy


def save_model(
    model,
    classes,
    hyperparameters,
    validation_accuracy,
    validation_balanced_accuracy,
    validation_loss,
    best_epoch,
    output_file,
):
    checkpoint = {
        "model_name": MODEL_NAME,
        "model_state": model.state_dict(),
        "classes": classes,
        "image_size": hyperparameters["image_size"],
        "mean": IMAGENET_MEAN,
        "std": IMAGENET_STD,
        "best_validation_accuracy": validation_accuracy,
        "best_validation_balanced_accuracy": validation_balanced_accuracy,
        "best_validation_loss": validation_loss,
        "best_epoch": best_epoch,
        "hyperparameters": hyperparameters,
    }

    torch.save(checkpoint, output_file)

    print(f"\nBest model saved to: {output_file}")
    print(
        f"Detection image size: "
        f"{checkpoint['image_size']}x{checkpoint['image_size']}"
    )


def run_stage(
    stage_number,
    train_samples,
    train_classes,
    validation_samples,
    validation_classes,
    test_samples,
    test_classes,
):
    print(f"\n\n{'=' * 70}")
    print(f"STARTING STAGE {stage_number}")
    print(f"{'=' * 70}")

    if stage_number == 1:
        search_space = STAGE1_SEARCH_SPACE
        output_file = STAGE1_BEST_FILE

    elif stage_number == 2:
        search_space = STAGE2_SEARCH_SPACE
        output_file = STAGE2_BEST_FILE

    elif stage_number == 3:
        search_space = STAGE3_SEARCH_SPACE
        output_file = STAGE3_BEST_FILE

    else:
        raise ValueError(f"Unsupported stage: {stage_number}")

    print(f"\nTraining images: {len(train_samples)}")
    print(f"Validation images: {len(validation_samples)}")
    print(f"Test images: {len(test_samples)}")

    print("\nClasses:")

    for index, class_name in enumerate(train_classes):
        print(f"  {index}: {class_name}")

    print("\nTraining distribution:")
    print_class_counts(train_samples, train_classes)

    results = []
    best_result = None
    best_model = None

    for trial in range(1, NUM_TUNING_TRIALS + 1):

        set_seed(RANDOM_SEED + stage_number * 1000 + trial)

        hyperparameters = sample_hyperparameters(search_space)

        trial_model = None

        try:

            result, trial_model = train_trial(
                stage_number,
                trial,
                hyperparameters,
                train_samples,
                train_classes,
                validation_samples,
                validation_classes,
            )

            results.append(result)

            if (
                best_result is None
                or result["best_validation_balanced_accuracy"]
                > best_result["best_validation_balanced_accuracy"]
            ):

                if best_model is not None:
                    cleanup_model(best_model)

                best_result = result
                best_model = trial_model
                trial_model = None

                print("\n*** NEW BEST TRIAL ***")
                print(
                    f"Validation balanced accuracy: "
                    f"{result['best_validation_balanced_accuracy']:.2f}%"
                )

        except RuntimeError as error:

            if "out of memory" in str(error).lower():

                print("\nCUDA OUT OF MEMORY.")
                print("Skipping this trial.")

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                continue

            raise

        finally:

            if trial_model is not None:
                cleanup_model(trial_model)

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    if best_result is None:

        print("\nNo successful trials.")
        return None

    results.sort(
        key=lambda x: x["best_validation_balanced_accuracy"], reverse=True
    )

    print(f"\n\n{'=' * 70}")
    print(f"STAGE {stage_number} TRIAL LEADERBOARD")
    print(f"{'=' * 70}")

    for index, result in enumerate(results, start=1):

        hp = result["hyperparameters"]

        print(f"\n#{index} Trial {result['trial']}")
        print(f"  Validation: {result['best_validation_accuracy']:.2f}%")
        print(
            f"  Validation balanced: "
            f"{result['best_validation_balanced_accuracy']:.2f}%"
        )
        print(f"  Image size: {hp['image_size']}")
        print(f"  LR: {hp['learning_rate']}")
        print(f"  Weight decay: {hp['weight_decay']}")
        print(f"  Label smoothing: {hp['label_smoothing']}")
        print(f"  Backbone LR multiplier: {hp['backbone_lr_multiplier']}")
        print(f"  Head-only epochs: {hp['head_only_epochs']}")
        print(f"  Scheduler: {hp['scheduler']}")

    save_model(
        best_model,
        train_classes,
        best_result["hyperparameters"],
        best_result["best_validation_accuracy"],
        best_result["best_validation_balanced_accuracy"],
        best_result["best_validation_loss"],
        best_result["best_epoch"],
        output_file,
    )

    hp = best_result["hyperparameters"]

    (
        test_accuracy,
        test_loss,
        test_class_accuracy,
        test_balanced_accuracy,
    ) = test_best_model(
        best_model,
        test_samples,
        test_classes,
        hp["image_size"],
        hp["label_smoothing"],
    )

    best_result["final_test_accuracy"] = test_accuracy
    best_result["final_test_balanced_accuracy"] = test_balanced_accuracy
    best_result["final_test_loss"] = test_loss
    best_result["final_test_class_accuracy"] = test_class_accuracy

    cleanup_model(best_model)
    best_model = None

    return {
        "stage": stage_number,
        "best_trial": best_result,
        "all_trials": results,
        "model_file": output_file,
    }


def load_stage_datasets(stage_number):
    if stage_number == 1:
        builder = build_stage1_dataset

    elif stage_number == 2:
        builder = build_fish_dataset

    elif stage_number == 3:
        builder = build_other_dataset

    else:
        raise ValueError(f"Unknown stage: {stage_number}")

    train_samples, train_classes = builder(TRAIN_DIR)
    validation_samples, validation_classes = builder(VALIDATION_DIR)
    test_samples, test_classes = builder(TEST_DIR)

    if train_classes != validation_classes:
        raise RuntimeError(
            f"Stage {stage_number} training and validation classes do not match.\n"
            f"Training: {train_classes}\n"
            f"Validation: {validation_classes}"
        )

    if train_classes != test_classes:
        raise RuntimeError(
            f"Stage {stage_number} training and test classes do not match.\n"
            f"Training: {train_classes}\n"
            f"Test: {test_classes}"
        )

    return (
        train_samples,
        train_classes,
        validation_samples,
        validation_classes,
        test_samples,
        test_classes,
    )


def main():
    total_start_time = time.time()

    set_seed(RANDOM_SEED)

    print(f"{'=' * 70}")
    print("3-STAGE RESNET18 HYPERPARAMETER TUNER")
    print(f"{'=' * 70}")

    print(f"\nDevice: {device}")

    if torch.cuda.is_available():

        print(f"GPU: {torch.cuda.get_device_name(0)}")

        gpu_memory = (
            torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        )

        print(f"VRAM: {gpu_memory:.1f} GB")
        print("Mixed precision: ENABLED")

    else:

        print("CUDA: DISABLED")

    print(f"\nStages: {TRAIN_STAGES}")
    print(f"Tuning trials per stage: {NUM_TUNING_TRIALS}")
    print(f"Maximum epochs per trial: {MAX_EPOCHS}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"DataLoader workers: {NUM_WORKERS}")
    print(f"RAM image cache: {USE_RAM_IMAGE_CACHE}")

    all_results = {}

    for stage_number in TRAIN_STAGES:

        (
            train_samples,
            train_classes,
            validation_samples,
            validation_classes,
            test_samples,
            test_classes,
        ) = load_stage_datasets(stage_number)

        print(f"\n\n{'=' * 70}")
        print(f"BUILDING STAGE {stage_number} DATASET")
        print(f"{'=' * 70}")

        print(f"\nTraining images: {len(train_samples)}")
        print(f"Validation images: {len(validation_samples)}")
        print(f"Test images: {len(test_samples)}")

        print("\nClasses:")

        for class_name in train_classes:
            print(f"  {class_name}")

        print("\nTraining distribution:")
        print_class_counts(train_samples, train_classes)

        result = run_stage(
            stage_number=stage_number,
            train_samples=train_samples,
            train_classes=train_classes,
            validation_samples=validation_samples,
            validation_classes=validation_classes,
            test_samples=test_samples,
            test_classes=test_classes,
        )

        all_results[f"stage_{stage_number}"] = result

        if torch.cuda.is_available():

            torch.cuda.empty_cache()

            try:
                torch.cuda.ipc_collect()
            except Exception:
                pass

        _IMAGE_CACHE.clear()

    with open(TUNING_RESULTS_FILE, "w", encoding="utf-8") as file:
        json.dump(all_results, file, indent=4)

    total_elapsed = time.time() - total_start_time

    print(f"\n\n{'=' * 70}")
    print("ALL THREE MODELS COMPLETE")
    print(f"{'=' * 70}")

    for stage_key, result in all_results.items():

        if result is None:
            continue

        best = result["best_trial"]
        hp = best["hyperparameters"]

        print(f"\n{stage_key.upper()}")
        print("-" * 50)
        print(f"Best trial: {best['trial']}")
        print(f"Validation accuracy: {best['best_validation_accuracy']:.2f}%")
        print(
            f"Validation balanced accuracy: "
            f"{best['best_validation_balanced_accuracy']:.2f}%"
        )
        print(f"Test accuracy: {best['final_test_accuracy']:.2f}%")
        print(
            f"Test balanced accuracy: "
            f"{best['final_test_balanced_accuracy']:.2f}%"
        )
        print(f"Image size: {hp['image_size']}x{hp['image_size']}")
        print(f"Learning rate: {hp['learning_rate']}")
        print(f"Weight decay: {hp['weight_decay']}")
        print(f"Label smoothing: {hp['label_smoothing']}")
        print(f"Backbone LR multiplier: {hp['backbone_lr_multiplier']}")
        print(f"Head-only epochs: {hp['head_only_epochs']}")
        print(f"Scheduler: {hp['scheduler']}")
        print(f"Model file: {result['model_file']}")

    print(f"\nResults saved to: {TUNING_RESULTS_FILE}")
    print(f"Total training time: {total_elapsed / 60:.1f} minutes")

    print(f"\n{'=' * 70}\nDONE\n{'=' * 70}")


if __name__ == "__main__":
    main()