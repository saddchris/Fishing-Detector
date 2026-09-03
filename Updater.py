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
from tkinter import messagebox


GITHUB_OWNER = "saddchris"
GITHUB_REPO = "Fishing-Detector"

APP_EXE = "FishingDet.exe"
UPDATER_EXE = "Updater.exe"

VERSION_FILE = "dist/FishingDet/version.json"

LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)


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

        return "0.0.0"


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


def get_latest_release():
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
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

        return json.loads(data)

    except urllib.error.HTTPError as error:
        print(
            f"GitHub HTTP error: "
            f"{error.code} {error.reason}"
        )

    except urllib.error.URLError as error:
        print(
            f"GitHub connection error: "
            f"{error.reason}"
        )

    except Exception as error:
        print(
            f"Could not get latest release: "
            f"{type(error).__name__}: {error}"
        )

    return None


def get_latest_version(release):
    if not release:
        return None

    tag_name = release.get("tag_name")

    if not tag_name:
        return None

    return str(tag_name).strip()


def update_available(latest_version):
    if not latest_version:
        return False

    current_version = get_current_version()

    latest_tuple = version_tuple(
        latest_version
    )

    current_tuple = version_tuple(
        current_version
    )

    print(
        f"Installed version: {current_version}"
    )

    print(
        f"Latest version:    {latest_version}"
    )

    return latest_tuple > current_tuple


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

    protected_directories = {
        "config",
        "configs",
        "data",
        "userdata",
        "user_data",
        "settings",
    }

    for part in parts[:-1]:
        if part.lower() in protected_directories:
            return True

    protected_files = {
        "config.json",
        "settings.json",
        "user_settings.json",
        "userdata.json",
        "user_data.json",
    }

    filename = parts[-1].lower()

    if filename in protected_files:
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

        self.root.title(
            "Fishing Detector Updater"
        )

        self.root.geometry(
            "500x220"
        )

        self.root.resizable(
            False,
            False,
        )

        self.current_version = current_version
        self.latest_version = latest_version

        title = tk.Label(
            root,
            text="Fishing Detector Update",
            font=(
                "Segoe UI",
                16,
                "bold",
            ),
        )

        title.pack(
            pady=(25, 10)
        )

        self.version_label = tk.Label(
            root,
            text=(
                f"Updating "
                f"{current_version} "
                f"→ "
                f"{latest_version}"
            ),
            font=(
                "Segoe UI",
                11,
            ),
        )

        self.version_label.pack(
            pady=5
        )

        self.status_label = tk.Label(
            root,
            text="Preparing update...",
            font=(
                "Segoe UI",
                10,
            ),
        )

        self.status_label.pack(
            pady=(15, 5)
        )

        self.progress = tk.DoubleVar(
            value=0
        )

        self.progress_bar = tk.Scale(
            root,
            variable=self.progress,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            showvalue=False,
            state=tk.DISABLED,
            length=400,
        )

        self.progress_bar.pack(
            pady=10
        )

    def set_status(self, text):
        try:
            self.root.after(
                0,
                lambda: self.status_label.config(
                    text=text
                ),
            )
        except Exception:
            pass

    def set_progress(self, value):
        try:
            self.root.after(
                0,
                lambda: self.progress.set(
                    value
                ),
            )
        except Exception:
            pass

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

        latest_version = (
            get_latest_version(release)
        )

        if not latest_version:
            raise RuntimeError(
                "GitHub release does not contain "
                "a valid version tag."
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
            version_tuple(installed_version)
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


def update_if_needed():
    install_directory = (
        get_install_directory()
    )

    updater_path = os.path.join(
        install_directory,
        UPDATER_EXE,
    )

    if not os.path.isfile(
        updater_path
    ):
        print(
            f"{UPDATER_EXE} not found. "
            "Skipping update."
        )

        return True

    current_version = (
        get_current_version()
    )

    print(
        f"Installed version: {current_version}"
    )

    release = get_latest_release()

    if not release:
        print(
            "Could not check GitHub release. "
            "Continuing without update."
        )

        return True

    latest_version = (
        get_latest_version(release)
    )

    if not latest_version:
        print(
            "GitHub release has no valid tag. "
            "Continuing without update."
        )

        return True

    print(
        f"Latest version: {latest_version}"
    )

    if not update_available(
        latest_version
    ):
        print(
            "Application is up to date."
        )

        return True

    print(
        f"Update available: "
        f"{current_version} -> "
        f"{latest_version}"
    )

    try:
        updater_process = subprocess.Popen(
            [
                updater_path,
                "--install-update",
            ],
            cwd=install_directory,
        )

        print(
            f"Updater started. PID: "
            f"{updater_process.pid}"
        )

        return False

    except Exception as error:
        print(
            f"Could not start updater: "
            f"{type(error).__name__}: {error}"
        )

        return True


def run_update_installer():
    root = tk.Tk()

    icon_path = get_updater_icon_path()

    if os.path.isfile(icon_path):
        try:
            root.iconbitmap(icon_path)
        except Exception:
            pass

    release = get_latest_release()

    if not release:
        messagebox.showerror(
            "Updater",
            "Could not retrieve the latest GitHub release.",
            parent=root,
        )

        root.destroy()
        return

    latest_version = (
        get_latest_version(release)
    )

    if not latest_version:
        messagebox.showerror(
            "Updater",
            "GitHub release does not contain a valid version.",
            parent=root,
        )

        root.destroy()
        return

    current_version = (
        get_current_version()
    )

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
    if "--install-update" in sys.argv:
        run_update_installer()
        return

    should_continue = update_if_needed()

    if should_continue is False:
        return

    install_directory = (
        get_install_directory()
    )

    app_path = os.path.join(
        install_directory,
        APP_EXE,
    )

    if os.path.isfile(
        app_path
    ):
        subprocess.Popen(
            [app_path],
            cwd=install_directory,
        )


if __name__ == "__main__":
    main()
