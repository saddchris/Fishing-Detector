import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import zipfile
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox


GITHUB_OWNER = "saddchris"
GITHUB_REPO = "Fishing-Detector"

APP_EXE = "FishingDet.exe"
UPDATER_EXE = "Updater.exe"

VERSION_FILE = "version.json"

PROTECTED_SETTINGS_FILENAME = "fishing_controller_settings.json"
PROTECTED_SETTINGS_PARENT_DIRS = {
    "configuration",
    "settings",
}

RELEASES_URL = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/releases"
)

BG_COLOR = "#15171c"
PANEL_COLOR = "#1c1f26"
ACCENT_COLOR = "#4f8dfd"
TEXT_COLOR = "#f2f3f5"
SUBTEXT_COLOR = "#9aa0ab"
TRACK_COLOR = "#2a2e37"


def get_install_directory():
    return os.path.dirname(
        os.path.abspath(sys.argv[0])
    )


def get_updater_icon_path():
    return os.path.join(
        get_install_directory(),
        "assets",
        "Updater.ico",
    )


def get_current_version():
    install_directory = get_install_directory()

    version_path = os.path.join(
        install_directory,
        VERSION_FILE,
    )

    try:
        with open(
            version_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        version = data.get("version")

        if not version:
            raise ValueError(
                "version.json does not contain a 'version' value."
            )

        return str(version).strip()

    except Exception as error:
        print(
            f"Could not read installed version: "
            f"{type(error).__name__}: {error}"
        )

        return None


def version_tuple(version):
    version = str(version).strip()

    if version.lower().startswith("v"):
        version = version[1:]

    parts = version.split(".")
    result = []

    for part in parts:
        digits = ""

        for character in part:
            if character.isdigit():
                digits += character
            else:
                break

        if digits:
            result.append(int(digits))
        else:
            result.append(0)

    return tuple(result)


def is_newer_version(candidate_version, current_version):
    if not candidate_version or not current_version:
        return False

    return (
        version_tuple(candidate_version)
        > version_tuple(current_version)
    )


def get_latest_release():
    request = urllib.request.Request(
        RELEASES_URL,
        headers={
            "User-Agent": "Fishing-Detector-Updater"
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            data = response.read().decode("utf-8")

        releases = json.loads(data)

    except urllib.error.HTTPError as error:
        print(
            f"GitHub HTTP error: "
            f"{error.code} {error.reason}"
        )
        return None

    except urllib.error.URLError as error:
        print(
            f"GitHub connection error: "
            f"{error.reason}"
        )
        return None

    except Exception as error:
        print(
            f"Could not get latest release: "
            f"{type(error).__name__}: {error}"
        )
        return None

    if not isinstance(releases, list) or not releases:
        print("No releases found on GitHub.")
        return None

    best_release = None
    best_version = None

    for release in releases:
        if release.get("draft"):
            continue

        if release.get("prerelease"):
            continue

        tag_name = release.get("tag_name")

        if not tag_name:
            continue

        candidate_version = version_tuple(tag_name)

        if best_version is None or candidate_version > best_version:
            best_version = candidate_version
            best_release = release

    if best_release is None:
        print("No usable non-draft, non-prerelease releases found.")

    return best_release


def get_latest_version(release):
    if not release:
        return None

    tag_name = release.get("tag_name")

    if not tag_name:
        return None

    return str(tag_name).strip()


def get_update_zip_asset(release):
    if not release:
        return None

    assets = release.get("assets", [])

    for asset in assets:
        name = asset.get("name", "")

        if name.lower().endswith(".zip"):
            return asset

    return None


def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Fishing-Detector-Updater"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=60,
    ) as response:
        with open(
            destination,
            "wb",
        ) as output:
            shutil.copyfileobj(
                response,
                output,
            )


def should_skip_path(relative_path):
    normalized = (
        relative_path
        .replace("\\", "/")
        .strip("/")
    )

    parts = normalized.split("/")

    if not parts:
        return False

    if normalized.lower() == UPDATER_EXE.lower():
        return True

    filename = parts[-1].lower()

    if filename == PROTECTED_SETTINGS_FILENAME.lower():
        parent_parts = [
            part.lower()
            for part in parts[:-1]
        ]

        for parent in parent_parts:
            if parent in PROTECTED_SETTINGS_PARENT_DIRS:
                return True

    return False


def copy_update_files(
    source_directory,
    install_directory,
    window=None,
):
    for root, directories, files in os.walk(
        source_directory
    ):
        relative_root = os.path.relpath(
            root,
            source_directory,
        )

        if relative_root == ".":
            relative_root = ""

        directories[:] = [
            directory
            for directory in directories
            if not should_skip_path(
                os.path.join(
                    relative_root,
                    directory,
                )
            )
        ]

        for directory in directories:
            relative_directory = os.path.join(
                relative_root,
                directory,
            )

            if should_skip_path(
                relative_directory
            ):
                continue

            destination_directory = os.path.join(
                install_directory,
                relative_directory,
            )

            os.makedirs(
                destination_directory,
                exist_ok=True,
            )

        for filename in files:
            relative_file = os.path.join(
                relative_root,
                filename,
            )

            if should_skip_path(
                relative_file
            ):
                continue

            source_file = os.path.join(
                source_directory,
                relative_file,
            )

            destination_file = os.path.join(
                install_directory,
                relative_file,
            )

            destination_parent = os.path.dirname(
                destination_file
            )

            os.makedirs(
                destination_parent,
                exist_ok=True,
            )

            if window:
                window.set_status(
                    f"Installing: {relative_file}"
                )

            shutil.copy2(
                source_file,
                destination_file,
            )


class UpdateWindow:

    def __init__(
        self,
        root,
        current_version,
        latest_version,
    ):
        self.root = root

        icon_path = get_updater_icon_path()

        if os.path.isfile(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.root.title("Fishing Detector Updater")
        self.root.geometry("480x300")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_COLOR)

        self.current_version = current_version
        self.latest_version = latest_version

        self._build_style()
        self._build_ui()

    def _build_style(self):
        style = ttk.Style(self.root)

        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Updater.Horizontal.TProgressbar",
            troughcolor=TRACK_COLOR,
            background=ACCENT_COLOR,
            bordercolor=TRACK_COLOR,
            lightcolor=ACCENT_COLOR,
            darkcolor=ACCENT_COLOR,
            thickness=10,
        )

    def _build_ui(self):
        outer = tk.Frame(
            self.root,
            bg=BG_COLOR,
        )
        outer.pack(fill="both", expand=True)

        header = tk.Frame(
            outer,
            bg=BG_COLOR,
        )
        header.pack(
            fill="x",
            padx=32,
            pady=(30, 4),
        )

        icon_dot = tk.Canvas(
            header,
            width=10,
            height=10,
            bg=BG_COLOR,
            highlightthickness=0,
        )
        icon_dot.create_oval(
            0, 0, 10, 10,
            fill=ACCENT_COLOR,
            outline="",
        )
        icon_dot.pack(side="left", pady=(6, 0))

        tk.Label(
            header,
            text="Fishing Detector",
            font=("Segoe UI", 17, "bold"),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            outer,
            text="An update is being installed",
            font=("Segoe UI", 10),
            bg=BG_COLOR,
            fg=SUBTEXT_COLOR,
        ).pack(
            anchor="w",
            padx=33,
            pady=(0, 20),
        )

        version_card = tk.Frame(
            outer,
            bg=PANEL_COLOR,
        )
        version_card.pack(
            fill="x",
            padx=32,
        )

        version_inner = tk.Frame(
            version_card,
            bg=PANEL_COLOR,
        )
        version_inner.pack(
            fill="x",
            padx=18,
            pady=14,
        )

        tk.Label(
            version_inner,
            text=self.current_version,
            font=("Segoe UI", 12, "bold"),
            bg=PANEL_COLOR,
            fg=SUBTEXT_COLOR,
        ).pack(side="left")

        tk.Label(
            version_inner,
            text="  →  ",
            font=("Segoe UI", 12, "bold"),
            bg=PANEL_COLOR,
            fg=ACCENT_COLOR,
        ).pack(side="left")

        tk.Label(
            version_inner,
            text=self.latest_version,
            font=("Segoe UI", 12, "bold"),
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
        ).pack(side="left")

        progress_frame = tk.Frame(
            outer,
            bg=BG_COLOR,
        )
        progress_frame.pack(
            fill="x",
            padx=32,
            pady=(26, 6),
        )

        self.progress = tk.DoubleVar(value=0)

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            style="Updater.Horizontal.TProgressbar",
            variable=self.progress,
            maximum=100,
            length=416,
            mode="determinate",
        )
        self.progress_bar.pack(fill="x")

        status_row = tk.Frame(
            outer,
            bg=BG_COLOR,
        )
        status_row.pack(
            fill="x",
            padx=32,
            pady=(10, 0),
        )

        self.status_label = tk.Label(
            status_row,
            text="Preparing update...",
            font=("Segoe UI", 9),
            bg=BG_COLOR,
            fg=SUBTEXT_COLOR,
            anchor="w",
            justify="left",
        )
        self.status_label.pack(side="left")

        self.percent_label = tk.Label(
            status_row,
            text="0%",
            font=("Segoe UI", 9, "bold"),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        )
        self.percent_label.pack(side="right")

        footer = tk.Label(
            outer,
            text="Please don't close this window",
            font=("Segoe UI", 8),
            bg=BG_COLOR,
            fg=SUBTEXT_COLOR,
        )
        footer.pack(
            side="bottom",
            pady=16,
        )

    def set_status(self, text):
        try:
            self.root.after(
                0,
                lambda: self.status_label.config(text=text),
            )
        except Exception:
            pass

    def set_progress(self, value):
        try:
            self.root.after(
                0,
                lambda: self._apply_progress(value),
            )
        except Exception:
            pass

    def _apply_progress(self, value):
        self.progress.set(value)
        self.percent_label.config(text=f"{int(value)}%")

    def close(self):
        try:
            self.root.after(
                0,
                self.root.destroy,
            )
        except Exception:
            pass


def update_worker(
    window,
    release,
):
    temporary_directory = None

    try:
        install_directory = (
            get_install_directory()
        )

        current_version = (
            get_current_version()
        )

        if current_version is None:
            raise RuntimeError(
                "Could not determine the installed version. "
                "Aborting update for safety."
            )

        latest_version = (
            get_latest_version(release)
        )

        if not latest_version:
            raise RuntimeError(
                "GitHub release does not contain "
                "a valid version tag."
            )

        if not is_newer_version(latest_version, current_version):
            raise RuntimeError(
                "Refusing to install: target version is not newer "
                "than the installed version.\n\n"
                f"Installed: {current_version}\n"
                f"Target: {latest_version}"
            )

        window.set_status(
            f"Current version: {current_version}"
        )

        time.sleep(0.5)

        asset = get_update_zip_asset(
            release
        )

        if not asset:
            raise RuntimeError(
                "No ZIP asset was found in "
                "the GitHub release."
            )

        download_url = asset.get(
            "browser_download_url"
        )

        if not download_url:
            raise RuntimeError(
                "The release ZIP does not have "
                "a valid download URL."
            )

        zip_filename = asset.get(
            "name",
            "update.zip",
        )

        temporary_directory = tempfile.mkdtemp(
            prefix="FishingDetectorUpdate_"
        )

        zip_path = os.path.join(
            temporary_directory,
            zip_filename,
        )

        extract_directory = os.path.join(
            temporary_directory,
            "extracted",
        )

        os.makedirs(
            extract_directory,
            exist_ok=True,
        )

        window.set_status(
            "Downloading update..."
        )

        download_file(
            download_url,
            zip_path,
        )

        window.set_progress(
            35
        )

        window.set_status(
            "Extracting update..."
        )

        with zipfile.ZipFile(
            zip_path,
            "r",
        ) as archive:
            archive.extractall(
                extract_directory
            )

        window.set_progress(
            55
        )

        extracted_items = os.listdir(
            extract_directory
        )

        if len(extracted_items) == 1:
            possible_directory = os.path.join(
                extract_directory,
                extracted_items[0],
            )

            if os.path.isdir(
                possible_directory
            ):
                source_directory = (
                    possible_directory
                )
            else:
                source_directory = (
                    extract_directory
                )
        else:
            source_directory = (
                extract_directory
            )

        update_version_path = os.path.join(
            source_directory,
            VERSION_FILE,
        )

        if not os.path.isfile(
            update_version_path
        ):
            raise RuntimeError(
                "The update ZIP does not contain "
                f"{VERSION_FILE}."
            )

        try:
            with open(
                update_version_path,
                "r",
                encoding="utf-8",
            ) as file:
                update_version_data = json.load(
                    file
                )

            package_version = str(
                update_version_data.get(
                    "version",
                    "",
                )
            ).strip()

        except Exception as error:
            raise RuntimeError(
                f"Invalid {VERSION_FILE}: "
                f"{error}"
            )

        if (
            version_tuple(package_version)
            != version_tuple(latest_version)
        ):
            raise RuntimeError(
                "Version mismatch detected.\n\n"
                f"GitHub release: {latest_version}\n"
                f"ZIP version: {package_version}"
            )

        if not is_newer_version(package_version, current_version):
            raise RuntimeError(
                "Refusing to install: package version is not newer "
                "than the installed version.\n\n"
                f"Installed: {current_version}\n"
                f"Package: {package_version}"
            )

        window.set_status(
            "Closing Fishing Detector..."
        )

        time.sleep(1)

        window.set_progress(
            65
        )

        window.set_status(
            "Installing update..."
        )

        copy_update_files(
            source_directory,
            install_directory,
            window,
        )

        window.set_progress(
            90
        )

        installed_version = (
            get_current_version()
        )

        if (
            installed_version is None
            or version_tuple(installed_version)
            != version_tuple(latest_version)
        ):
            raise RuntimeError(
                "Update completed, but the installed "
                "version could not be verified.\n\n"
                f"Expected: {latest_version}\n"
                f"Installed: {installed_version}"
            )

        window.set_progress(
            100
        )

        window.set_status(
            f"Update complete: {installed_version}"
        )

        time.sleep(1)

        app_path = os.path.join(
            install_directory,
            APP_EXE,
        )

        if not os.path.isfile(
            app_path
        ):
            raise RuntimeError(
                f"{APP_EXE} was not found after "
                "the update."
            )

        subprocess.Popen(
            [
                app_path,
                "--updated",
            ],
            cwd=install_directory,
        )

        window.close()

    except Exception as error:
        print(
            f"Update failed: "
            f"{type(error).__name__}: {error}"
        )

        def show_error():
            messagebox.showerror(
                "Update Failed",
                (
                    "The update could not be installed.\n\n"
                    f"{type(error).__name__}: {error}"
                ),
                parent=window.root,
            )

            window.root.destroy()

        try:
            window.root.after(
                0,
                show_error,
            )
        except Exception:
            pass

    finally:
        if temporary_directory:
            try:
                shutil.rmtree(
                    temporary_directory,
                    ignore_errors=True,
                )
            except Exception:
                pass


def check_update_needed():
    current_version = get_current_version()

    if current_version is None:
        return False

    release = get_latest_release()

    latest_version = get_latest_version(release)

    if latest_version is None:
        return False

    return is_newer_version(latest_version, current_version)


def launch_app():
    install_directory = get_install_directory()

    app_path = os.path.join(
        install_directory,
        APP_EXE,
    )

    if not os.path.isfile(app_path):
        print(f"{APP_EXE} not found.")
        return False

    try:
        subprocess.Popen(
            [app_path],
            cwd=install_directory,
        )

        return True

    except Exception as error:
        print(
            f"Could not start {APP_EXE}: "
            f"{type(error).__name__}: {error}"
        )

        return False


def launch_updater_and_exit():
    install_directory = get_install_directory()

    updater_path = os.path.join(
        install_directory,
        UPDATER_EXE,
    )

    if not os.path.isfile(updater_path):
        print(f"{UPDATER_EXE} not found.")
        return False

    try:
        updater_process = subprocess.Popen(
            [updater_path],
            cwd=install_directory,
        )

        print(
            f"Updater started. PID: "
            f"{updater_process.pid}"
        )

        return True

    except Exception as error:
        print(
            f"Could not start updater: "
            f"{type(error).__name__}: {error}"
        )

        return False


def run_update_installer(release, current_version, latest_version):
    root = tk.Tk()

    icon_path = get_updater_icon_path()

    if os.path.isfile(icon_path):
        try:
            root.iconbitmap(icon_path)
        except Exception:
            pass

    window = UpdateWindow(
        root,
        current_version,
        latest_version,
    )

    thread = threading.Thread(
        target=update_worker,
        args=(
            window,
            release,
        ),
        daemon=True,
    )

    thread.start()

    root.mainloop()


def main():
    current_version = get_current_version()

    release = None
    latest_version = None

    if current_version is not None:
        release = get_latest_release()
        latest_version = get_latest_version(release)

    if (
        current_version is not None
        and latest_version is not None
        and is_newer_version(latest_version, current_version)
    ):
        run_update_installer(
            release,
            current_version,
            latest_version,
        )
        return

    launch_app()


if __name__ == "__main__":
    main()