from pathlib import Path
import json

import torch
from torch import nn
from torchvision import models


BASE_DIR = Path(__file__).resolve().parent.parent

MODELS_DIR = (
    BASE_DIR
    / "configuration"
    / "models"
)

MODEL_CLASSES_FILE = (
    MODELS_DIR
    / "model_classes.json"
)

MODEL_FILES = [
    "stage1_model.pth",
    "fish_model.pth",
    "other_model.pth",
]


def convert_model(
    model_file,
):
    input_file = (
        MODELS_DIR
        / model_file
    )

    output_file = (
        MODELS_DIR
        / model_file.replace(
            ".pth",
            ".onnx",
        )
    )

    print()
    print(
        f"Processing: {model_file}"
    )

    checkpoint = torch.load(
        input_file,
        map_location="cpu",
    )

    classes = list(
        checkpoint["classes"]
    )

    print(
        f"Classes: {classes}"
    )

    model = models.resnet18(
        weights=None
    )

    model.fc = nn.Linear(
        model.fc.in_features,
        len(classes),
    )

    model.load_state_dict(
        checkpoint["model_state"]
    )

    model.eval()

    image_size = checkpoint.get(
        "image_size",
        224,
    )

    dummy_input = torch.randn(
        1,
        3,
        image_size,
        image_size,
    )

    torch.onnx.export(
        model,
        dummy_input,
        output_file,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {
                0: "batch_size"
            },
            "output": {
                0: "batch_size"
            },
        },
        opset_version=17,
    )

    print(
        f"Converted: {input_file}"
    )

    print(
        f"Created:   {output_file}"
    )

    print(
        f"Classes:   {len(classes)}"
    )

    return classes


def main():

    model_classes = {}

    for model_file in MODEL_FILES:

        classes = convert_model(
            model_file,
        )

        model_name = (
            Path(model_file).stem
        )

        model_classes[
            model_name
        ] = classes

    with open(
        MODEL_CLASSES_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            model_classes,
            file,
            indent=4,
        )

    print()
    print(
        "================================"
    )
    print(
        "Conversion completed successfully."
    )
    print(
        f"Class mapping saved to:"
    )
    print(
        MODEL_CLASSES_FILE
    )
    print(
        "================================"
    )


if __name__ == "__main__":
    main()