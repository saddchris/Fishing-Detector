import time

from pathlib import Path
import torch
from PIL import Image, ImageGrab
from torch import nn
from torchvision import models, transforms


from Paths import (
    MODELS_DIR,
    CONFIG_IMAGES_DIR,
)


STAGE1_MODEL_FILE = (
    MODELS_DIR / "stage1_model.pth"
)

FISH_MODEL_FILE = (
    MODELS_DIR / "fish_model.pth"
)

OTHER_MODEL_FILE = (
    MODELS_DIR / "other_model.pth"
)

MASK_FILE = (
    CONFIG_IMAGES_DIR / "FishingRod_Mask.png"
)

IMAGE_SIZE = 224
FISH_CONFIDENCE_THRESHOLD = 40.0
OTHER_CONFIDENCE_THRESHOLD = 40.0

CROP_SIZES = {
    "small": (0.35, 0.45),
    "medium": (0.55, 0.65),
    "large": (0.75, 0.85),
}


class FishDetector:

    def __init__(
        self,
        wanted_fish=None,
        wanted_other=None,
    ):

        self.wanted_fish = set(
            wanted_fish or []
        )

        self.wanted_other = set(
            wanted_other or []
        )

        self.device = torch.device("cpu")

        self.transform = transforms.Compose(
            [
                transforms.Resize(
                    (
                        IMAGE_SIZE,
                        IMAGE_SIZE,
                    )
                ),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[
                        0.485,
                        0.456,
                        0.406,
                    ],
                    std=[
                        0.229,
                        0.224,
                        0.225,
                    ],
                ),
            ]
        )

        try:

            self.mask = Image.open(
                MASK_FILE
            ).convert(
                "RGBA"
            )

        except Exception as error:

            raise RuntimeError(
                f"Could not load mask "
                f"'{MASK_FILE}': {error}"
            ) from error

        self.stage1_model = None
        self.stage1_classes = None

        self.fish_model = None
        self.fish_classes = None

        self.other_model = None
        self.other_classes = None

        self.models_loaded = False

    def apply_mask(
        self,
        image,
    ):

        image = (
            image.convert("RGB")
            if image.mode != "RGB"
            else image
        )

        mask = self.mask

        if mask.size != image.size:

            mask = mask.resize(
                image.size,
                Image.Resampling.NEAREST,
            )

        alpha = mask.getchannel(
            "A"
        )

        black = Image.new(
            "RGB",
            image.size,
            (0, 0, 0),
        )

        return Image.composite(
            black,
            image,
            alpha,
        )

    def load_model(
        self,
        model_file,
    ):

        print(
            f"Loading model: {model_file}"
        )

        checkpoint = torch.load(
            model_file,
            map_location=self.device,
        )

        try:

            classes = list(
                checkpoint.get(
                    "classes",
                    [],
                )
            )

            state_dict = checkpoint.get(
                "model_state"
            )

            if not classes:

                raise RuntimeError(
                    f"Model '{model_file}' "
                    "contains no classes."
                )

            if state_dict is None:

                raise RuntimeError(
                    f"Model '{model_file}' "
                    "does not contain "
                    "'model_state'."
                )

            model = models.resnet18(
                weights=None
            )

            model.fc = nn.Linear(
                model.fc.in_features,
                len(classes),
            )

            model.load_state_dict(
                state_dict
            )

            model.to(
                self.device
            )

            model.eval()

            return (
                model,
                classes,
            )

        finally:

            del checkpoint

    def unload_models(
        self,
    ):

        self.stage1_model = None
        self.stage1_classes = None

        self.fish_model = None
        self.fish_classes = None

        self.other_model = None
        self.other_classes = None

        self.models_loaded = False

        if torch.cuda.is_available():

            torch.cuda.empty_cache()

    def set_targets(
        self,
        fish_targets,
        other_targets,
    ):

        fish_targets = set(
            fish_targets
        )

        other_targets = set(
            other_targets
        )

        if self.fish_classes is not None:

            invalid_fish = (
                fish_targets
                - set(self.fish_classes)
            )

            if invalid_fish:

                raise ValueError(
                    "Invalid fish targets: "
                    f"{sorted(invalid_fish)}"
                )

        if self.other_classes is not None:

            invalid_other = (
                other_targets
                - set(self.other_classes)
            )

            if invalid_other:

                raise ValueError(
                    "Invalid other targets: "
                    f"{sorted(invalid_other)}"
                )

        self.wanted_fish = fish_targets
        self.wanted_other = other_targets

    def load_values(
        self,
        fish_targets,
        other_targets,
    ):

        fish_targets = set(
            fish_targets
        )

        other_targets = set(
            other_targets
        )

        self.unload_models()

        self.wanted_fish = fish_targets
        self.wanted_other = other_targets

        try:

            (
                self.stage1_model,
                self.stage1_classes,
            ) = self.load_model(
                STAGE1_MODEL_FILE
            )

            (
                self.fish_model,
                self.fish_classes,
            ) = self.load_model(
                FISH_MODEL_FILE
            )

            (
                self.other_model,
                self.other_classes,
            ) = self.load_model(
                OTHER_MODEL_FILE
            )

            invalid_fish = (
                fish_targets
                - set(self.fish_classes)
            )

            if invalid_fish:

                raise ValueError(
                    "Selected fish are not "
                    "present in fish_model.pth: "
                    f"{sorted(invalid_fish)}"
                )

            invalid_other = (
                other_targets
                - set(self.other_classes)
            )

            if invalid_other:

                raise ValueError(
                    "Selected other targets "
                    "are not present in "
                    "other_model.pth: "
                    f"{sorted(invalid_other)}"
                )

            self.models_loaded = True

            return True

        except Exception:

            self.unload_models()

            raise

    def ensure_models_loaded(
        self,
    ):

        if not self.models_loaded:

            raise RuntimeError(
                "Models have not been loaded."
            )

        for name, model in (
            (
                "stage 1",
                self.stage1_model,
            ),
            (
                "fish",
                self.fish_model,
            ),
            (
                "other",
                self.other_model,
            ),
        ):

            if model is None:

                raise RuntimeError(
                    f"{name.capitalize()} "
                    "model is not loaded."
                )

    @staticmethod
    def crop_center(
        image,
        width_percent,
        height_percent,
    ):

        width, height = image.size

        crop_width = max(
            1,
            int(
                width * width_percent
            ),
        )

        crop_height = max(
            1,
            int(
                height * height_percent
            ),
        )

        left = (
            width - crop_width
        ) // 2

        top = (
            height - crop_height
        ) // 2

        return image.crop(
            (
                left,
                top,
                left + crop_width,
                top + crop_height,
            )
        )

    def _predict_batch(
        self,
        images,
        model,
        classes,
    ):

        if model is None:

            raise RuntimeError(
                "Prediction requested "
                "before model loading."
            )

        if not classes:

            raise RuntimeError(
                "Prediction requested "
                "with no classes."
            )

        tensors = torch.stack(
            [
                self.transform(image)
                for image in images
            ]
        )

        tensors = tensors.to(
            self.device,
            non_blocking=(
                self.device.type == "cuda"
            ),
        )

        with torch.inference_mode():

            probabilities = (
                torch.softmax(
                    model(tensors),
                    dim=1,
                )
            )

        confidences, predicted = (
            torch.max(
                probabilities,
                dim=1,
            )
        )

        categories = [
            classes[index]
            for index in predicted.tolist()
        ]

        return (
            categories,
            confidences.mul(
                100.0
            ),
            probabilities,
        )

    def predict_image(
        self,
        image,
        model,
        classes,
    ):

        (
            categories,
            confidences,
            probabilities,
        ) = self._predict_batch(
            [image],
            model,
            classes,
        )

        return (
            categories[0],
            confidences[0].item(),
            probabilities[0],
        )

    def run_stage1(
        self,
        screenshot,
    ):

        self.ensure_models_loaded()

        crop_names = list(
            CROP_SIZES
        )

        crops = [
            self.crop_center(
                screenshot,
                *CROP_SIZES[name],
            )
            for name in crop_names
        ]

        (
            _,
            _,
            probabilities,
        ) = self._predict_batch(
            crops,
            self.stage1_model,
            self.stage1_classes,
        )

        average_probabilities = (
            probabilities.mean(
                dim=0
            )
        )

        (
            ensemble_confidence,
            ensemble_index,
        ) = torch.max(
            average_probabilities,
            dim=0,
        )

        ensemble_category = (
            self.stage1_classes[
                ensemble_index.item()
            ]
        )

        ensemble_confidence = (
            ensemble_confidence.item()
            * 100.0
        )

        return (
            ensemble_category,
            ensemble_confidence,
            crops,
        )

    def run_fish_model(
        self,
        images,
    ):

        self.ensure_models_loaded()

        (
            _,
            _,
            probabilities,
        ) = self._predict_batch(
            images,
            self.fish_model,
            self.fish_classes,
        )

        average_probabilities = (
            probabilities.mean(
                dim=0
            )
        )

        (
            confidence,
            predicted,
        ) = torch.max(
            average_probabilities,
            dim=0,
        )

        category = self.fish_classes[
            predicted.item()
        ]

        confidence = (
            confidence.item()
            * 100.0
        )

        if (
            confidence
            < FISH_CONFIDENCE_THRESHOLD
        ):

            return (
                "unknown_fish",
                confidence,
            )

        return (
            category,
            confidence,
        )

    def run_other_model(
        self,
        images,
    ):

        self.ensure_models_loaded()

        (
            _,
            _,
            probabilities,
        ) = self._predict_batch(
            images,
            self.other_model,
            self.other_classes,
        )

        average_probabilities = (
            probabilities.mean(
                dim=0
            )
        )

        (
            confidence,
            predicted,
        ) = torch.max(
            average_probabilities,
            dim=0,
        )

        category = self.other_classes[
            predicted.item()
        ]

        confidence = (
            confidence.item()
            * 100.0
        )

        if (
            confidence
            < OTHER_CONFIDENCE_THRESHOLD
        ):

            return (
                "unknown_other",
                confidence,
            )

        return (
            category,
            confidence,
        )

    def detect_catch(
        self,
        should_continue=None,
    ):

        self.ensure_models_loaded()

        end_time = (
            time.monotonic()
            + 1.0
        )

        while (
            time.monotonic()
            < end_time
        ):

            if (
                should_continue is not None
                and not should_continue()
            ):

                return (
                    "cancelled",
                    0.0,
                    False,
                )

            remaining = (
                end_time
                - time.monotonic()
            )

            time.sleep(
                min(
                    0.02,
                    max(
                        0.0,
                        remaining,
                    ),
                )
            )

        if (
            should_continue is not None
            and not should_continue()
        ):

            return (
                "cancelled",
                0.0,
                False,
            )

        screenshot = (
            ImageGrab.grab()
            .convert("RGB")
        )

        screenshot = self.apply_mask(
            screenshot
        )

        (
            stage1_category,
            stage1_confidence,
            crops,
        ) = self.run_stage1(
            screenshot
        )

        if (
            should_continue is not None
            and not should_continue()
        ):

            return (
                "cancelled",
                0.0,
                False,
            )

        if stage1_category == "fish":

            (
                category,
                confidence,
            ) = self.run_fish_model(
                crops
            )

            if category == "unknown_fish":

                return (
                    category,
                    confidence,
                    False,
                )

            return (
                category,
                confidence,
                category
                in self.wanted_fish,
            )

        if stage1_category == "other":

            (
                category,
                confidence,
            ) = self.run_other_model(
                crops
            )

            if category == "unknown_other":

                return (
                    category,
                    confidence,
                    False,
                )

            return (
                category,
                confidence,
                category
                in self.wanted_other,
            )

        return (
            stage1_category,
            stage1_confidence,
            False,
        )