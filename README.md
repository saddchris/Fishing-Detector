# Fishing Controller

A Python-based fishing automation controller with a graphical interface, computer-vision bait detection, configurable fishing targets, and automatic bait management.

The application is designed to control the fishing process through a desktop GUI while using detection models and screen-based image matching to identify fishing events and available bait.

---

## Features

- Graphical fishing controller built with Tkinter
- Fish and other target selection
- YOLO/detection-model based target detection
- Automatic bait management
- Computer-vision bait identification using OpenCV template matching
- Configurable bait inventory points
- Enable/disable individual bait inventory slots
- Automatic bait equipping
- Configurable delay between fishing actions
- Start/stop fishing controls
- Five-second startup countdown
- Emergency stop handling
- Keyboard hotkeys for starting/stopping
- Live application output/log window
- Model loading performed separately from starting the fishing process
- Persistent application settings
- Centralised project paths through `Paths.py`

---

## Project Structure

```text
Fishing Controller/
│
├── GUIController.py
├── Main.py
├── Detection.py
├── BaitManager.py
├── WindowsInput.py
├── Paths.py
│
├── configuration/
│   ├── models/
│   │   ├── ...
│   │
│   ├── config_images/
│   │   ├── ...
│   │
│   ├── bait_images/
│   │   ├── Screenshot_Cod.png
│   │   ├── Screenshot_Gold.png
│   │   ├── Screenshot_Snapper.png
│   │   ├── Screenshot_Trout.png
│   │   ├── Screenshot_Tuna.png
│   │   └── Screenshot_Tiger.png
│   │
│   └── settings/
│       ├── fishing_controller_settings.json
│       └── bait_manager_settings.json
│
└── README.md
