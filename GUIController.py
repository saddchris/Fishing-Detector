import json
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox

import Main
import BaitManager

from Paths import SETTINGS_DIR, ICON_FILE


WINDOW_TITLE = "Fishing Controller"

WINDOW_WIDTH = 700
WINDOW_HEIGHT = 980

BG_COLOR = "#1e1e1e"
TEXT_COLOR = "#ffffff"
SECONDARY_COLOR = "#aaaaaa"
ENTRY_BG = "#2b2b2b"
BUTTON_BG = "#333333"
BUTTON_ACTIVE = "#444444"

STOPPED_COLOR = "#ff4444"
ACTIVE_COLOR = "#44dd66"
STARTING_COLOR = "#ffaa00"
LOADED_COLOR = "#55aaff"

DEFAULT_ACTION_DELAY = 3.0
MIN_ACTION_DELAY = 0.1
MAX_ACTION_DELAY = 60.0

SETTINGS_FILE = SETTINGS_DIR / "fishing_controller_settings.json"
CLASSES_FILE = SETTINGS_DIR / "classes.json"


def get_bait_points():
    return BaitManager.get_bait_points()


def get_available_targets():
    try:
        with open(CLASSES_FILE, "r", encoding="utf-8") as file:
            classes = json.load(file)

        fish_targets = classes.get("fish_targets", [])
        other_targets = classes.get("other_targets", [])

        return (
            list(dict.fromkeys(fish_targets)),
            list(dict.fromkeys(other_targets)),
        )

    except Exception as error:
        print(
            f"Could not read classes from {CLASSES_FILE}: {error}"
        )
        return [], []


FISH_TARGETS, OTHER_TARGETS = get_available_targets()


class FishingControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=BG_COLOR)

        try:
            if ICON_FILE.exists():
                self.root.iconbitmap(str(ICON_FILE))
        except Exception as error:
            print(f"Could not load application icon: {error}")

        self.root.resizable(False, False)

        self.countdown_job = None
        self.countdown_running = False
        self.countdown_remaining = 0

        self.gui_closing = False
        self.load_in_progress = False

        self.pending_action_delay = DEFAULT_ACTION_DELAY

        self.bait_points_expanded = True

        self.log_queue = queue.Queue()

        self._stdout = sys.stdout
        sys.stdout = GuiOutput(self)

        self._build_ui()
        self._load_settings()

        self.delay_var.trace_add(
            "write",
            lambda *_: self._save_settings(),
        )

        Main.set_state_callback(self.main_state_changed)
        Main.set_exit_callback(self.close_gui_from_main)

        Main.install_hotkeys()

        self._log("Fishing Controller started.\n")
        self._log(f"Found {len(FISH_TARGETS)} fish classes.\n")
        self._log(f"Found {len(OTHER_TARGETS)} other classes.\n")

        self.root.protocol("WM_DELETE_WINDOW", self.close_gui)

        self.root.after(50, self._process_log_queue)
        self.root.after(100, self._monitor_state)

    def _build_ui(self):
        tk.Label(
            self.root,
            text="FISHING CONTROLLER",
            font=("Arial", 20, "bold"),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        ).pack(pady=(18, 3))

        status_frame = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        status_frame.pack(pady=(2, 10))

        tk.Label(
            status_frame,
            text="Status:",
            font=("Arial", 12),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        ).pack(side="left")

        self.status_value = tk.Label(
            status_frame,
            text="STOPPED",
            font=("Arial", 12, "bold"),
            bg=BG_COLOR,
            fg=STOPPED_COLOR,
        )
        self.status_value.pack(side="left", padx=(6, 0))

        model_status_frame = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        model_status_frame.pack(pady=(0, 12))

        tk.Label(
            model_status_frame,
            text="Models:",
            font=("Arial", 10),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        ).pack(side="left")

        self.model_status_value = tk.Label(
            model_status_frame,
            text="NOT LOADED",
            font=("Arial", 10, "bold"),
            bg=BG_COLOR,
            fg=SECONDARY_COLOR,
        )
        self.model_status_value.pack(side="left", padx=(6, 0))

        tk.Label(
            self.root,
            text="TARGETS",
            font=("Arial", 14, "bold"),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        ).pack(pady=(0, 3))

        targets_container = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        targets_container.pack(
            padx=30,
            fill="both",
        )

        self.fish_vars = {}
        self.other_vars = {}

        self._build_target_panel(
            targets_container,
            " FISH ",
            FISH_TARGETS,
            self.fish_vars,
            True,
        )

        self._build_target_panel(
            targets_container,
            " OTHER ",
            OTHER_TARGETS,
            self.other_vars,
            False,
        )

        target_button_frame = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        target_button_frame.pack(pady=10)

        self.select_all_button = self._button(
            target_button_frame,
            "Select All",
            self.select_all_targets,
        )
        self.select_all_button.pack(side="left", padx=4)

        self.clear_all_button = self._button(
            target_button_frame,
            "Clear All",
            self.clear_all_targets,
        )
        self.clear_all_button.pack(side="left", padx=4)

        self.select_fish_button = self._button(
            target_button_frame,
            "All Fish",
            self.select_all_fish,
        )
        self.select_fish_button.pack(side="left", padx=4)

        self.clear_fish_button = self._button(
            target_button_frame,
            "Clear Fish",
            self.clear_all_fish,
        )
        self.clear_fish_button.pack(side="left", padx=4)

        self._build_bait_points_ui()

        delay_frame = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        delay_frame.pack(pady=(3, 7))

        tk.Label(
            delay_frame,
            text="Delay before next cast:",
            font=("Arial", 10),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        ).pack(side="left", padx=(0, 8))

        self.delay_var = tk.DoubleVar(
            value=DEFAULT_ACTION_DELAY
        )

        self.delay_spinbox = tk.Spinbox(
            delay_frame,
            from_=MIN_ACTION_DELAY,
            to=MAX_ACTION_DELAY,
            increment=0.1,
            textvariable=self.delay_var,
            width=8,
            bg=ENTRY_BG,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            buttonbackground=BUTTON_BG,
            font=("Arial", 10),
        )
        self.delay_spinbox.pack(side="left")

        tk.Label(
            delay_frame,
            text="seconds",
            font=("Arial", 10),
            bg=BG_COLOR,
            fg=SECONDARY_COLOR,
        ).pack(side="left", padx=(5, 0))

        bait_frame = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        bait_frame.pack(pady=(4, 8))

        self.auto_bait_var = tk.BooleanVar(value=False)

        self.auto_bait_checkbox = tk.Checkbutton(
            bait_frame,
            text="Auto Equip Bait",
            variable=self.auto_bait_var,
            command=self._auto_bait_changed,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            selectcolor="#444444",
            activebackground=BG_COLOR,
            activeforeground=TEXT_COLOR,
            font=("Arial", 11, "bold"),
        )
        self.auto_bait_checkbox.pack()

        tk.Label(
            bait_frame,
            text="Checks bait before fishing and after catches.",
            font=("Arial", 8),
            bg=BG_COLOR,
            fg=SECONDARY_COLOR,
        ).pack(pady=(2, 0))

        tk.Label(
            self.root,
            text="OUTPUT",
            font=("Arial", 12, "bold"),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        ).pack(pady=(8, 4))

        log_frame = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        log_frame.pack(
            padx=25,
            fill="both",
            expand=True,
        )

        self.log_text = tk.Text(
            log_frame,
            height=7,
            bg="#111111",
            fg="#dddddd",
            insertbackground=TEXT_COLOR,
            font=("Consolas", 9),
            borderwidth=0,
            highlightthickness=0,
            state="disabled",
        )

        scrollbar = tk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log_text.yview,
        )

        self.log_text.configure(
            yscrollcommand=scrollbar.set
        )

        self.log_text.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        button_frame = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        button_frame.pack(pady=10)

        self.load_button = self._button(
            button_frame,
            "LOAD VALUES",
            self.load_values,
            bg="#285b8b",
            activebackground="#3474ad",
            width=18,
            height=2,
        )
        self.load_button.pack(side="left", padx=6)

        self.start_button = self._button(
            button_frame,
            "START FISHING",
            self.start_fishing,
            bg="#286b3b",
            activebackground="#35894c",
            width=18,
            height=2,
            state="disabled",
        )
        self.start_button.pack(side="left", padx=6)

        self.stop_button = self._button(
            button_frame,
            "STOP",
            self.stop_fishing,
            bg="#8b3030",
            activebackground="#aa3b3b",
            width=12,
            height=2,
        )
        self.stop_button.pack(side="left", padx=6)

    def _build_bait_points_ui(self):
        bait_points = get_bait_points()

        self.bait_points_frame = tk.LabelFrame(
            self.root,
            text=" BAIT POINTS ",
            font=("Arial", 11, "bold"),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            bd=1,
            relief="groove",
        )
        self.bait_points_frame.pack(
            padx=30,
            pady=(0, 8),
            fill="x",
        )

        header = tk.Frame(
            self.bait_points_frame,
            bg=BG_COLOR,
        )
        header.pack(
            fill="x",
            padx=8,
            pady=(3, 2),
        )

        self.bait_points_toggle_button = self._button(
            header,
            "Hide",
            self.toggle_bait_points,
            width=8,
        )
        self.bait_points_toggle_button.pack(
            side="right"
        )

        self.bait_points_status = tk.Label(
            header,
            text=f"{len(bait_points)} bait points selected",
            font=("Arial", 9),
            bg=BG_COLOR,
            fg=SECONDARY_COLOR,
        )
        self.bait_points_status.pack(side="left")

        self.bait_points_content = tk.Frame(
            self.bait_points_frame,
            bg=BG_COLOR,
        )
        self.bait_points_content.pack(fill="x")

        self.bait_point_vars = {}
        self.bait_point_widgets = {}

        bait_grid = tk.Frame(
            self.bait_points_content,
            bg=ENTRY_BG,
        )
        bait_grid.pack(
            padx=8,
            pady=6,
            fill="x",
        )

        for index, point in enumerate(
            bait_points,
            start=1,
        ):
            var = tk.BooleanVar(
                value=BaitManager.get_bait_point_enabled(
                    point
                )
            )

            self.bait_point_vars[index] = var

            checkbox = tk.Checkbutton(
                bait_grid,
                text=f"{index}: {point[0]}, {point[1]}",
                variable=var,
                command=self._bait_points_changed,
                bg=ENTRY_BG,
                fg=TEXT_COLOR,
                selectcolor="#444444",
                activebackground=ENTRY_BG,
                activeforeground=TEXT_COLOR,
                font=("Arial", 8),
                anchor="w",
            )

            self.bait_point_widgets[index] = checkbox

            row = (index - 1) // 5
            column = (index - 1) % 5

            checkbox.grid(
                row=row,
                column=column,
                sticky="w",
                padx=5,
                pady=2,
            )

        bait_button_frame = tk.Frame(
            self.bait_points_content,
            bg=BG_COLOR,
        )
        bait_button_frame.pack(pady=(2, 7))

        self.select_all_bait_button = self._button(
            bait_button_frame,
            "Select All Bait Points",
            self.select_all_bait_points,
        )
        self.select_all_bait_button.pack(
            side="left",
            padx=4,
        )

        self.clear_all_bait_button = self._button(
            bait_button_frame,
            "Clear All Bait Points",
            self.clear_all_bait_points,
        )
        self.clear_all_bait_button.pack(
            side="left",
            padx=4,
        )

        self._update_bait_point_status()

    def toggle_bait_points(self):
        if self.bait_points_expanded:
            self.bait_points_content.pack_forget()
            self.bait_points_toggle_button.config(text="Show")
            self.bait_points_expanded = False
        else:
            self.bait_points_content.pack(fill="x")
            self.bait_points_toggle_button.config(text="Hide")
            self.bait_points_expanded = True

        self._update_bait_point_status()

    def _update_bait_point_status(self):
        selected = sum(
            1
            for variable in self.bait_point_vars.values()
            if variable.get()
        )

        self.bait_points_status.config(
            text=(
                f"{selected} bait point"
                f"{'' if selected == 1 else 's'} selected"
            )
        )

    def _button(
        self,
        parent,
        text,
        command,
        **kwargs,
    ):
        bg = kwargs.pop("bg", BUTTON_BG)
        activebackground = kwargs.pop(
            "activebackground",
            BUTTON_ACTIVE,
        )

        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=TEXT_COLOR,
            activebackground=activebackground,
            activeforeground=TEXT_COLOR,
            font=("Arial", 10),
            **kwargs,
        )

    def _build_target_panel(
        self,
        parent,
        title,
        targets,
        variables,
        left,
    ):
        section = tk.LabelFrame(
            parent,
            text=title,
            font=("Arial", 11, "bold"),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            bd=1,
            relief="groove",
        )

        section.pack(
            side="left" if left else "right",
            fill="both",
            expand=left,
            padx=(0, 8) if left else (8, 0),
        )

        canvas = tk.Canvas(
            section,
            bg=ENTRY_BG,
            highlightthickness=0,
            height=280,
        )

        scrollbar = tk.Scrollbar(
            section,
            orient="vertical",
            command=canvas.yview,
        )

        canvas.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        inner = tk.Frame(
            canvas,
            bg=ENTRY_BG,
        )

        canvas.create_window(
            (0, 0),
            window=inner,
            anchor="nw",
        )

        inner.bind(
            "<Configure>",
            lambda _event, c=canvas:
            c.configure(
                scrollregion=c.bbox("all")
            ),
        )

        for target in targets:
            var = tk.BooleanVar(value=False)
            variables[target] = var

            tk.Checkbutton(
                inner,
                text=target,
                variable=var,
                command=self._save_settings,
                bg=ENTRY_BG,
                fg=TEXT_COLOR,
                selectcolor="#444444",
                activebackground=ENTRY_BG,
                activeforeground=TEXT_COLOR,
                font=("Arial", 10),
                anchor="w",
            ).pack(
                fill="x",
                padx=8,
                pady=2,
            )

    def _bait_points_changed(self):
        bait_points = get_bait_points()

        for index, variable in self.bait_point_vars.items():
            if index < 1 or index > len(bait_points):
                continue

            BaitManager.set_bait_point_enabled_by_index(
                index,
                variable.get(),
            )

        self._update_bait_point_status()
        self._save_settings()

    def select_all_bait_points(self):
        bait_points = get_bait_points()

        for index in range(1, len(bait_points) + 1):
            self.bait_point_vars[index].set(True)

            BaitManager.set_bait_point_enabled_by_index(
                index,
                True,
            )

        self._update_bait_point_status()
        self._save_settings()

    def clear_all_bait_points(self):
        bait_points = get_bait_points()

        for index in range(1, len(bait_points) + 1):
            self.bait_point_vars[index].set(False)

            BaitManager.set_bait_point_enabled_by_index(
                index,
                False,
            )

        self._update_bait_point_status()
        self._save_settings()

    def _apply_bait_points(self, selected_points):
        bait_points = get_bait_points()

        valid_selected_points = set()

        for point in selected_points:
            try:
                point = int(point)
            except (TypeError, ValueError):
                continue

            if 1 <= point <= len(bait_points):
                valid_selected_points.add(point)

        for index in range(1, len(bait_points) + 1):
            enabled = index in valid_selected_points

            if index in self.bait_point_vars:
                self.bait_point_vars[index].set(enabled)

            BaitManager.set_bait_point_enabled_by_index(
                index,
                enabled,
            )

        self._update_bait_point_status()

    def _log(self, message):
        if message:
            self.log_queue.put(message)

    def _process_log_queue(self):
        if self.gui_closing:
            return

        try:
            while True:
                message = self.log_queue.get_nowait()

                self.log_text.configure(state="normal")
                self.log_text.insert(tk.END, message)
                self.log_text.see(tk.END)
                self.log_text.configure(state="disabled")

        except queue.Empty:
            pass

        if not self.gui_closing:
            self.root.after(
                50,
                self._process_log_queue,
            )

    def _save_settings(self):
        if self.gui_closing:
            return

        try:
            settings = {
                "fish_targets": [
                    target
                    for target, variable in self.fish_vars.items()
                    if variable.get()
                ],
                "other_targets": [
                    target
                    for target, variable in self.other_vars.items()
                    if variable.get()
                ],
                "action_delay": self.delay_var.get(),
                "auto_bait": self.auto_bait_var.get(),
                "bait_points": [
                    index
                    for index, variable in self.bait_point_vars.items()
                    if variable.get()
                ],
            }

            SETTINGS_FILE.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with open(
                SETTINGS_FILE,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    settings,
                    file,
                    indent=4,
                )

        except Exception as error:
            try:
                self._stdout.write(
                    f"Could not save settings: {error}\n"
                )
            except Exception:
                pass

    def _load_settings(self):
        if not SETTINGS_FILE.exists():
            self._apply_bait_points(
                range(
                    1,
                    len(get_bait_points()) + 1,
                )
            )
            return

        try:
            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8",
            ) as file:
                settings = json.load(file)

            saved_fish = set(
                settings.get(
                    "fish_targets",
                    [],
                )
            )

            saved_other = set(
                settings.get(
                    "other_targets",
                    [],
                )
            )

            for target, variable in self.fish_vars.items():
                variable.set(target in saved_fish)

            for target, variable in self.other_vars.items():
                variable.set(target in saved_other)

            try:
                value = float(
                    settings.get(
                        "action_delay",
                        DEFAULT_ACTION_DELAY,
                    )
                )
            except (TypeError, ValueError):
                value = DEFAULT_ACTION_DELAY

            self.delay_var.set(
                max(
                    MIN_ACTION_DELAY,
                    min(
                        MAX_ACTION_DELAY,
                        value,
                    ),
                )
            )

            auto_bait = bool(
                settings.get(
                    "auto_bait",
                    False,
                )
            )

            self.auto_bait_var.set(auto_bait)

            saved_bait_points = settings.get(
                "bait_points",
                None,
            )

            if saved_bait_points is None:
                saved_bait_points = range(
                    1,
                    len(get_bait_points()) + 1,
                )

            self._apply_bait_points(
                saved_bait_points
            )

            Main.set_auto_bait_enabled(
                auto_bait
            )

        except Exception as error:
            try:
                self._stdout.write(
                    f"Could not load saved settings: {error}\n"
                )
            except Exception:
                pass

    def _auto_bait_changed(self):
        enabled = self.auto_bait_var.get()

        Main.set_auto_bait_enabled(enabled)

        self._save_settings()

        self._log(
            f"Auto Equip Bait: {'ON' if enabled else 'OFF'}\n"
        )

    def _set_controls(self, enabled):
        state = "normal" if enabled else "disabled"

        for button in (
            self.select_all_button,
            self.clear_all_button,
            self.select_fish_button,
            self.clear_fish_button,
            self.select_all_bait_button,
            self.clear_all_bait_button,
            self.bait_points_toggle_button,
        ):
            button.config(state=state)

        self.delay_spinbox.config(state=state)
        self.auto_bait_checkbox.config(state=state)

        for widget in self.bait_point_widgets.values():
            widget.config(state=state)

    def _selected_targets(self):
        return (
            [
                target
                for target, variable in self.fish_vars.items()
                if variable.get()
            ],
            [
                target
                for target, variable in self.other_vars.items()
                if variable.get()
            ],
        )

    def _action_delay(self):
        try:
            value = float(self.delay_var.get())
        except (TypeError, ValueError):
            self._log("Invalid delay value.\n")
            return None

        value = max(
            MIN_ACTION_DELAY,
            min(
                MAX_ACTION_DELAY,
                value,
            ),
        )

        self.delay_var.set(value)
        self._save_settings()

        return value

    def _models_loaded(self):
        detector = getattr(
            Main,
            "detector",
            None,
        )

        return bool(
            detector
            and getattr(
                Main,
                "values_loaded",
                False,
            )
            and getattr(
                detector,
                "models_loaded",
                False,
            )
        )

    def select_all_targets(self):
        for variable in (
            *self.fish_vars.values(),
            *self.other_vars.values(),
        ):
            variable.set(True)

        self._save_settings()

    def clear_all_targets(self):
        for variable in (
            *self.fish_vars.values(),
            *self.other_vars.values(),
        ):
            variable.set(False)

        self._save_settings()

    def select_all_fish(self):
        for variable in self.fish_vars.values():
            variable.set(True)

        self._save_settings()

    def clear_all_fish(self):
        for variable in self.fish_vars.values():
            variable.set(False)

        self._save_settings()

    def load_values(self):
        if self.gui_closing or self.load_in_progress:
            return

        if self.countdown_running:
            messagebox.showwarning(
                "Starting",
                "Stop the countdown before loading values.",
            )
            return

        if Main.is_worker_running():
            messagebox.showwarning(
                "Fishing Active",
                "Stop fishing before loading values.",
            )
            return

        selected_fish, selected_other = self._selected_targets()

        if not selected_fish and not selected_other:
            messagebox.showwarning(
                "No Targets",
                "Select at least one target before loading values.",
            )
            return

        if not any(
            variable.get()
            for variable in self.bait_point_vars.values()
        ):
            messagebox.showwarning(
                "No Bait Points",
                "Select at least one bait point.",
            )
            return

        if self._action_delay() is None:
            return

        self.load_in_progress = True

        self.load_button.config(state="disabled")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        self._set_controls(False)

        self.status_value.config(
            text="LOADING",
            fg=STARTING_COLOR,
        )

        self.model_status_value.config(
            text="LOADING...",
            fg=STARTING_COLOR,
        )

        threading.Thread(
            target=self._load_values_thread,
            args=(
                selected_fish,
                selected_other,
            ),
            name="ModelLoader",
            daemon=True,
        ).start()

    def _load_values_thread(
        self,
        selected_fish,
        selected_other,
    ):
        try:
            self._log(
                "Loading detector and models...\n"
            )

            if not Main.load_values(
                selected_fish,
                selected_other,
            ):
                raise RuntimeError(
                    "Main.load_values() returned False."
                )

            self.root.after(
                0,
                self._values_loaded_successfully,
            )

        except Exception as error:
            self._log(
                "ERROR WHILE LOADING MODELS: "
                f"{type(error).__name__}: {error}\n"
            )

            self.root.after(
                0,
                self._values_load_failed,
            )

    def _values_loaded_successfully(self):
        if self.gui_closing:
            return

        self.load_in_progress = False

        self.status_value.config(
            text="STOPPED",
            fg=STOPPED_COLOR,
        )

        self.model_status_value.config(
            text="LOADED",
            fg=LOADED_COLOR,
        )

        self.load_button.config(state="normal")
        self.start_button.config(state="normal")
        self.stop_button.config(state="normal")

        self._set_controls(True)

    def _values_load_failed(self):
        if self.gui_closing:
            return

        self.load_in_progress = False

        self.status_value.config(
            text="STOPPED",
            fg=STOPPED_COLOR,
        )

        self.model_status_value.config(
            text="LOAD FAILED",
            fg=STOPPED_COLOR,
        )

        self.load_button.config(state="normal")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        self._set_controls(True)

    def start_fishing(self):
        if (
            self.gui_closing
            or self.load_in_progress
            or self.countdown_running
        ):
            return

        if (
            Main.is_worker_running()
            or getattr(
                Main,
                "enabled",
                False,
            )
        ):
            self._log(
                "Fishing is already active.\n"
            )
            return

        if not self._models_loaded():
            messagebox.showwarning(
                "Models Not Loaded",
                "Select targets and click LOAD VALUES first.",
            )
            return

        if not any(
            variable.get()
            for variable in self.bait_point_vars.values()
        ):
            messagebox.showwarning(
                "No Bait Points",
                "Select at least one bait point.",
            )
            return

        delay = self._action_delay()

        if delay is None:
            return

        self.pending_action_delay = delay

        self.countdown_running = True
        self.countdown_remaining = 5

        self.load_button.config(state="disabled")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        self._set_controls(False)

        self.status_value.config(
            text="STARTING",
            fg=STARTING_COLOR,
        )

        self._log(
            "Starting fishing in 5 seconds...\n"
        )

        self._update_countdown()

    def _update_countdown(self):
        if (
            self.gui_closing
            or not self.countdown_running
        ):
            return

        if getattr(
            Main,
            "shutdown_requested",
            False,
        ):
            self.cancel_countdown(False)
            return

        if self.countdown_remaining <= 0:
            self.countdown_running = False
            self.countdown_job = None

            self._log(
                "Starting fishing now...\n"
            )

            if Main.start_fishing_worker(
                self.pending_action_delay
            ):
                self._fishing_started()
            else:
                self._fishing_stopped()

            return

        self._log(
            f"Starting in {self.countdown_remaining}...\n"
        )

        self.countdown_remaining -= 1

        self.countdown_job = self.root.after(
            1000,
            self._update_countdown,
        )

    def cancel_countdown(self, write_log=True):
        self.countdown_running = False
        self.countdown_remaining = 0

        if self.countdown_job is not None:
            try:
                self.root.after_cancel(
                    self.countdown_job
                )
            except tk.TclError:
                pass

            self.countdown_job = None

        if write_log:
            self._log(
                "START CANCELLED.\n"
            )

    def _fishing_started(self):
        if self.gui_closing:
            return

        self.status_value.config(
            text="ACTIVE",
            fg=ACTIVE_COLOR,
        )

        self.load_button.config(state="disabled")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        self._set_controls(False)

    def stop_fishing(self):
        if self.gui_closing:
            return

        if self.countdown_running:
            self.cancel_countdown()

        Main.stop()

        self._fishing_stopped()

    def _fishing_stopped(self):
        if self.gui_closing:
            return

        if self.countdown_running:
            self.cancel_countdown(False)

        self.status_value.config(
            text="STOPPED",
            fg=STOPPED_COLOR,
        )

        self.stop_button.config(state="normal")

        if self.load_in_progress:
            self.load_button.config(state="disabled")
            self.start_button.config(state="disabled")
            self._set_controls(False)
            return

        self.load_button.config(state="normal")

        self._set_controls(True)

        if self._models_loaded():
            self.start_button.config(state="normal")

            self.model_status_value.config(
                text="LOADED",
                fg=LOADED_COLOR,
            )
        else:
            self.start_button.config(state="disabled")

            self.model_status_value.config(
                text="NOT LOADED",
                fg=SECONDARY_COLOR,
            )

    def main_state_changed(self, active):
        if self.gui_closing:
            return

        try:
            self.root.after(
                0,
                lambda: self._apply_main_state(active),
            )
        except tk.TclError:
            pass

    def _apply_main_state(self, active):
        if self.gui_closing:
            return

        if active:
            self._fishing_started()
        elif not self.countdown_running:
            self._fishing_stopped()

    def _monitor_state(self):
        if self.gui_closing:
            return

        if getattr(
            Main,
            "shutdown_requested",
            False,
        ):
            if self.countdown_running:
                self.cancel_countdown(False)

            self.status_value.config(
                text="STOPPED",
                fg=STOPPED_COLOR,
            )

            self.load_button.config(state="disabled")
            self.start_button.config(state="disabled")
            self.stop_button.config(state="disabled")

            self._set_controls(False)
            return

        if self.load_in_progress:
            self.status_value.config(
                text="LOADING",
                fg=STARTING_COLOR,
            )

            self.model_status_value.config(
                text="LOADING...",
                fg=STARTING_COLOR,
            )

        elif (
            self.countdown_running
            or Main.is_worker_running()
            or getattr(
                Main,
                "enabled",
                False,
            )
        ):
            self.status_value.config(
                text=(
                    "STARTING"
                    if self.countdown_running
                    else "ACTIVE"
                ),
                fg=(
                    STARTING_COLOR
                    if self.countdown_running
                    else ACTIVE_COLOR
                ),
            )

        else:
            self._fishing_stopped()

        if not self.gui_closing:
            self.root.after(
                150,
                self._monitor_state,
            )

    def close_gui_from_main(self):
        if self.gui_closing:
            return

        try:
            self.root.after(
                0,
                self.close_gui,
            )
        except tk.TclError:
            pass

    def close_gui(self):
        if self.gui_closing:
            return

        self._save_settings()

        self.gui_closing = True

        self.cancel_countdown(False)

        try:
            Main.emergency_exit()
        except Exception as error:
            try:
                self._stdout.write(
                    f"Shutdown error: {error}\n"
                )
            except Exception:
                pass

        sys.stdout = self._stdout

        try:
            self.root.destroy()
        except tk.TclError:
            pass


class GuiOutput:
    def __init__(self, app):
        self.app = app

    def write(self, text):
        if text:
            self.app._log(text)

    def flush(self):
        return None


def main():
    root = tk.Tk()
    FishingControllerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()