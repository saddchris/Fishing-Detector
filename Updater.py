import sys
import os
import time
import shutil
import zipfile
import tempfile
import subprocess
import urllib.request
import json
import tkinter as tk
from tkinter import ttk


GITHUB_OWNER = "saddchris"
GITHUB_REPO = "Fishing-Detector"

APP_EXE = "FishingDet.exe"
UPDATER_EXE = "Updater.exe"
CURRENT_VERSION = "1.1.0"

LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)

PROTECTED_CONFIG_FOLDERS = {
    "bait_images",
    "config_images",
}

PROTECTED_CONFIG_FILES = {
    "fishing_controller_settings.json",
}


def get_latest_release():
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={
            "User-Agent": "FishingDet-Updater",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def version_tuple(version):
    version = version.lower().strip()

    if version.startswith("v"):
        version = version[1:]

    parts = version.split(".")
    result = []

    for part in parts:
        number = ""

        for character in part:
            if character.isdigit():
                number += character
            else:
                break

        result.append(
            int(number or 0)
        )

    while len(result) < 3:
        result.append(0)

    return tuple(result[:3])


def update_available(latest_version):
    return (
        version_tuple(latest_version)
        > version_tuple(CURRENT_VERSION)
    )


class UpdaterWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FishingDet Updater")
        self.root.geometry("520x210")
        self.root.resizable(False, False)

        self.status = tk.StringVar(
            value="Checking for updates..."
        )

        self.file_name = tk.StringVar(
            value=""
        )

        self.progress = ttk.Progressbar(
            self.root,
            orient="horizontal",
            length=460,
            mode="determinate",
        )

        self.progress.pack(
            padx=30,
            pady=(35, 10),
        )

        ttk.Label(
            self.root,
            textvariable=self.status,
        ).pack(
            padx=30,
            pady=5,
        )

        ttk.Label(
            self.root,
            textvariable=self.file_name,
        ).pack(
            padx=30,
            pady=5,
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.disable_close,
        )

    def disable_close(self):
        pass

    def set_status(self, text):
        self.status.set(text)
        self.root.update_idletasks()

    def set_file(self, text):
        self.file_name.set(text)
        self.root.update_idletasks()

    def set_progress(self, value):
        self.progress["value"] = value
        self.root.update_idletasks()

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


def download_file(
    url,
    destination,
    window,
):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "FishingDet-Updater",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=60,
    ) as response:

        total_size = response.headers.get(
            "Content-Length"
        )

        total_size = (
            int(total_size)
            if total_size
            else None
        )

        downloaded = 0

        with open(
            destination,
            "wb",
        ) as file:

            while True:
                data = response.read(
                    1024 * 1024
                )

                if not data:
                    break

                file.write(data)
                downloaded += len(data)

                if total_size:
                    percentage = (
                        downloaded
                        / total_size
                        * 100
                    )

                    window.set_progress(
                        percentage
                    )

                    window.set_status(
                        f"Downloading update... "
                        f"{percentage:.1f}%"
                    )

    window.set_progress(100)


def is_application_running():
    try:
        processes = subprocess.run(
            [
                "tasklist",
                "/FI",
                f"IMAGENAME eq {APP_EXE}",
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        return APP_EXE.lower() in (
            processes.stdout.lower()
        )

    except Exception:
        return False


def close_application(window):
    window.set_status(
        "Closing FishingDet..."
    )

    try:
        subprocess.run(
            [
                "taskkill",
                "/F",
                "/IM",
                APP_EXE,
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        pass

    for _ in range(60):
        if not is_application_running():
            return True

        time.sleep(0.5)

        try:
            window.root.update()
        except Exception:
            pass

    return False


def wait_for_application_to_close(window):
    window.set_status(
        "Waiting for FishingDet to close..."
    )

    for _ in range(60):
        if not is_application_running():
            return True

        time.sleep(0.5)

        try:
            window.root.update()
        except Exception:
            pass

    return False


def should_skip_path(relative_path):
    normalized = relative_path.replace(
        "\\",
        "/",
    ).strip("/")

    parts = normalized.split("/")

    if not parts:
        return False

    if normalized.lower() == UPDATER_EXE.lower():
        return True

    if (
        len(parts) >= 2
        and parts[0].lower() == "configuration"
    ):
        if (
            parts[1].lower()
            in PROTECTED_CONFIG_FOLDERS
        ):
            return True

        if (
            len(parts) == 3
            and parts[1].lower() == "settings"
            and parts[2].lower()
            in {
                filename.lower()
                for filename
                in PROTECTED_CONFIG_FILES
            }
        ):
            return True

    return False


def extract_update(
    zip_path,
    install_directory,
    window,
):
    temporary_directory = tempfile.mkdtemp(
        prefix="FishingDetUpdate_"
    )

    try:
        with zipfile.ZipFile(
            zip_path,
            "r",
        ) as archive:
            archive.extractall(
                temporary_directory
            )

        extracted_items = os.listdir(
            temporary_directory
        )

        if (
            len(extracted_items) == 1
            and os.path.isdir(
                os.path.join(
                    temporary_directory,
                    extracted_items[0],
                )
            )
        ):
            source_directory = os.path.join(
                temporary_directory,
                extracted_items[0],
            )
        else:
            source_directory = (
                temporary_directory
            )

        files = []

        for root, directories, filenames in os.walk(
            source_directory
        ):
            relative_root = os.path.relpath(
                root,
                source_directory,
            )

            if relative_root == ".":
                relative_root = ""

            remaining_directories = []

            for directory in directories:
                relative_directory = os.path.join(
                    relative_root,
                    directory,
                )

                if not should_skip_path(
                    relative_directory
                ):
                    remaining_directories.append(
                        directory
                    )

            directories[:] = remaining_directories

            for filename in filenames:
                relative_file = os.path.join(
                    relative_root,
                    filename,
                )

                if should_skip_path(
                    relative_file
                ):
                    continue

                files.append(
                    (
                        root,
                        filename,
                        relative_file,
                    )
                )

        total_files = len(files)

        for index, (
            root,
            filename,
            relative_file,
        ) in enumerate(
            files,
            start=1,
        ):
            source = os.path.join(
                root,
                filename,
            )

            destination = os.path.join(
                install_directory,
                relative_file,
            )

            destination_directory = os.path.dirname(
                destination
            )

            os.makedirs(
                destination_directory,
                exist_ok=True,
            )

            window.set_file(
                f"{relative_file} "
                f"({index}/{total_files})"
            )

            window.set_status(
                "Installing update..."
            )

            shutil.copy2(
                source,
                destination,
            )

            percentage = (
                index
                / total_files
                * 100
            ) if total_files else 100

            window.set_progress(
                percentage
            )

    finally:
        shutil.rmtree(
            temporary_directory,
            ignore_errors=True,
        )


def start_application(
    install_directory,
):
    application = os.path.join(
        install_directory,
        APP_EXE,
    )

    if not os.path.exists(application):
        return False

    subprocess.Popen(
        [
            application,
            "--updated",
        ],
        cwd=install_directory,
    )

    return True


def show_error(
    window,
    message,
):
    window.set_status(
        message
    )

    window.set_file("")

    time.sleep(3)


def main():
    window = UpdaterWindow()

    try:
        window.set_status(
            f"Current version: {CURRENT_VERSION}"
        )

        try:
            release = get_latest_release()

        except Exception as error:
            show_error(
                window,
                f"Could not check for updates: {error}",
            )
            return False

        latest_version = release.get(
            "tag_name",
            "",
        )

        if not latest_version:
            show_error(
                window,
                "Could not determine latest version.",
            )
            return False

        window.set_status(
            f"Latest version: {latest_version}"
        )

        if not update_available(
            latest_version
        ):
            window.set_progress(100)

            window.set_status(
                f"Already running the latest version "
                f"({latest_version})."
            )

            window.set_file("")

            time.sleep(1)

            return True

        assets = release.get(
            "assets",
            [],
        )

        zip_asset = None

        for asset in assets:
            name = asset.get(
                "name",
                "",
            )

            if name.lower().endswith(
                ".zip"
            ):
                zip_asset = asset
                break

        if zip_asset is None:
            show_error(
                window,
                "No ZIP update was found in the GitHub release.",
            )
            return False

        download_url = zip_asset.get(
            "browser_download_url"
        )

        if not download_url:
            show_error(
                window,
                "Release ZIP has no download URL.",
            )
            return False

        install_directory = os.path.dirname(
            os.path.abspath(
                sys.argv[0]
            )
        )

        temporary_zip = os.path.join(
            tempfile.gettempdir(),
            "FishingDet_Update.zip",
        )

        window.set_status(
            f"Update available: {latest_version}"
        )

        window.set_file(
            zip_asset.get(
                "name",
                "FishingDet update",
            )
        )

        window.set_progress(0)

        try:
            download_file(
                download_url,
                temporary_zip,
                window,
            )

        except Exception as error:
            show_error(
                window,
                f"Download failed: {error}",
            )
            return False

        if is_application_running():
            if not close_application(
                window
            ):
                show_error(
                    window,
                    "FishingDet did not close in time.",
                )
                return False

        if not wait_for_application_to_close(
            window
        ):
            show_error(
                window,
                "FishingDet is still running.",
            )
            return False

        try:
            extract_update(
                temporary_zip,
                install_directory,
                window,
            )

        except Exception as error:
            show_error(
                window,
                f"Update installation failed: {error}",
            )
            return False

        try:
            os.remove(
                temporary_zip
            )
        except Exception:
            pass

        window.set_progress(100)

        window.set_status(
            f"Updated successfully to "
            f"{latest_version}."
        )

        window.set_file(
            "Starting FishingDet..."
        )

        time.sleep(1)

        return start_application(
            install_directory
        )

    finally:
        window.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass