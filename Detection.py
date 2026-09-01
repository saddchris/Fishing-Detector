import time
import json

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageGrab

from Paths import (
MODELS_DIR,
CONFIG_IMAGES_DIR,
)

STAGE1_MODEL_FILE = (
MODELS_DIR / "stage1_model.onnx"
)

FISH_MODEL_FILE = (
MODELS_DIR / "fish_model.onnx"
)

OTHER_MODEL_FILE = (
MODELS_DIR / "other_model.onnx"
)

MODEL_CLASSES_FILE = (
MODELS_DIR / "model_classes.json"
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

        self.device = "CPUExecutionProvider"

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
        self.stage1_input_name = None
        self.stage1_output_name = None

        self.fish_model = None
        self.fish_classes = None
        self.fish_input_name = None
        self.fish_output_name = None

        self.other_model = None
        self.other_classes = None
        self.other_input_name = None
        self.other_output_name = None

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
        model_name,
        model_classes,
    ):

        print(
            f"Loading model: {model_file}"
        )

        if not model_file.exists():

            raise FileNotFoundError(
                f"Model file not found: "
                f"'{model_file}'"
            )

        classes = list(
            model_classes.get(
                model_name,
                [],
            )
        )

        if not classes:

            raise RuntimeError(
                f"No classes found for "
                f"'{model_name}' in "
                f"'{MODEL_CLASSES_FILE}'."
            )

        try:

            session = (
                ort.InferenceSession(
                    str(model_file),
                    providers=[
                        self.device
                    ],
                )
            )

        except Exception as error:

            raise RuntimeError(
                f"Could not load ONNX model "
                f"'{model_file}': {error}"
            ) from error

        inputs = session.get_inputs()

        if len(inputs) != 1:

            raise RuntimeError(
                f"Model '{model_file}' must "
                "have exactly one input."
            )

        input_name = inputs[0].name

        outputs = session.get_outputs()

        if len(outputs) != 1:

            raise RuntimeError(
                f"Model '{model_file}' must "
                "have exactly one output."
            )

        output_name = outputs[0].name
        output_shape = outputs[0].shape

        if len(output_shape) != 2:

            raise RuntimeError(
                f"Model '{model_file}' has "
                f"unexpected output shape: "
                f"{output_shape}"
            )

        output_class_count = (
            output_shape[1]
        )

        if (
            isinstance(
                output_class_count,
                int,
            )
            and output_class_count
            != len(classes)
        ):

            raise RuntimeError(
                f"Class count mismatch for "
                f"'{model_file}'. "
                f"Model output: {output_shape}, "
                f"classes: {len(classes)}"
            )

        return (
            session,
            classes,
            input_name,
            output_name,
        )

    def unload_models(
        self,
    ):

        self.stage1_model = None
        self.stage1_classes = None
        self.stage1_input_name = None
        self.stage1_output_name = None

        self.fish_model = None
        self.fish_classes = None
        self.fish_input_name = None
        self.fish_output_name = None

        self.other_model = None
        self.other_classes = None
        self.other_input_name = None
        self.other_output_name = None

        self.models_loaded = False

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

        if not MODEL_CLASSES_FILE.exists():

            raise FileNotFoundError(
                f"Model classes file not found: "
                f"'{MODEL_CLASSES_FILE}'"
            )

        try:

            with open(
                MODEL_CLASSES_FILE,
                "r",
                encoding="utf-8",
            ) as file:

                model_classes = json.load(
                    file
                )

        except Exception as error:

            raise RuntimeError(
                f"Could not load model classes "
                f"'{MODEL_CLASSES_FILE}': {error}"
            ) from error

        try:

            (
                self.stage1_model,
                self.stage1_classes,
                self.stage1_input_name,
                self.stage1_output_name,
            ) = self.load_model(
                STAGE1_MODEL_FILE,
                "stage1_model",
                model_classes,
            )

            (
                self.fish_model,
                self.fish_classes,
                self.fish_input_name,
                self.fish_output_name,
            ) = self.load_model(
                FISH_MODEL_FILE,
                "fish_model",
                model_classes,
            )

            (
                self.other_model,
                self.other_classes,
                self.other_input_name,
                self.other_output_name,
            ) = self.load_model(
                OTHER_MODEL_FILE,
                "other_model",
                model_classes,
            )

            invalid_fish = (
                fish_targets
                - set(self.fish_classes)
            )

            if invalid_fish:

                raise ValueError(
                    "Selected fish are not "
                    "present in fish_model: "
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
                    "other_model: "
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

    def _prepare_image(
        self,
        image,
    ):

        image = image.convert(
            "RGB"
        )

        image = image.resize(
            (
                IMAGE_SIZE,
                IMAGE_SIZE,
            ),
            Image.Resampling.BILINEAR,
        )

        array = np.asarray(
            image,
            dtype=np.float32,
        )

        array /= 255.0

        mean = np.array(
            [
                0.485,
                0.456,
                0.406,
            ],
            dtype=np.float32,
        )

        std = np.array(
            [
                0.229,
                0.224,
                0.225,
            ],
            dtype=np.float32,
        )

        array = (
            array - mean
        ) / std

        array = np.transpose(
            array,
            (
                2,
                0,
                1,
            ),
        )

        return array

    @staticmethod
    def _softmax(
        values,
    ):

        values = np.asarray(
            values,
            dtype=np.float32,
        )

        values = (
            values
            - np.max(
                values,
                axis=1,
                keepdims=True,
            )
        )

        exponential = np.exp(
            values
        )

        return (
            exponential
            / exponential.sum(
                axis=1,
                keepdims=True,
            )
        )

    def _predict_batch(
        self,
        images,
        model,
        classes,
        input_name,
        output_name,
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

        if not images:

            raise RuntimeError(
                "Prediction requested "
                "with no images."
            )

        tensors = np.stack(
            [
                self._prepare_image(
                    image
                )
                for image in images
            ]
        ).astype(
            np.float32
        )

        outputs = model.run(
            [output_name],
            {
                input_name: tensors
            },
        )

        logits = np.asarray(
            outputs[0],
            dtype=np.float32,
        )

        if (
            logits.ndim != 2
            or logits.shape[1]
            != len(classes)
        ):

            raise RuntimeError(
                "ONNX output shape does "
                "not match class count. "
                f"Output shape: {logits.shape}, "
                f"classes: {len(classes)}"
            )

        probabilities = (
            self._softmax(
                logits
            )
        )

        predicted = np.argmax(
            probabilities,
            axis=1,
        )

        confidences = (
            probabilities[
                np.arange(
                    len(predicted)
                ),
                predicted,
            ]
            * 100.0
        )

        categories = [
            classes[index]
            for index in predicted
        ]

        return (
            categories,
            confidences,
            probabilities,
        )

    def predict_image(
        self,
        image,
        model,
        classes,
        input_name,
        output_name,
    ):

        (
            categories,
            confidences,
            probabilities,
        ) = self._predict_batch(
            [image],
            model,
            classes,
            input_name,
            output_name,
        )

        return (
            categories[0],
            float(
                confidences[0]
            ),
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
            self.stage1_input_name,
            self.stage1_output_name,
        )

        average_probabilities = (
            probabilities.mean(
                axis=0
            )
        )

        ensemble_index = int(
            np.argmax(
                average_probabilities
            )
        )

        ensemble_confidence = (
            float(
                average_probabilities[
                    ensemble_index
                ]
            )
            * 100.0
        )

        ensemble_category = (
            self.stage1_classes[
                ensemble_index
            ]
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
            self.fish_input_name,
            self.fish_output_name,
        )

        average_probabilities = (
            probabilities.mean(
                axis=0
            )
        )

        predicted = int(
            np.argmax(
                average_probabilities
            )
        )

        confidence = (
            float(
                average_probabilities[
                    predicted
                ]
            )
            * 100.0
        )

        category = self.fish_classes[
            predicted
        ]

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
            self.other_input_name,
            self.other_output_name,
        )

        average_probabilities = (
            probabilities.mean(
                axis=0
            )
        )

        predicted = int(
            np.argmax(
                average_probabilities
            )
        )

        confidence = (
            float(
                average_probabilities[
                    predicted
                ]
            )
            * 100.0
        )

        category = self.other_classes[
            predicted
        ]

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
