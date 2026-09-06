"""
Universal AI Memory Hub - Auto-Updater Module
Checks for updates from the official GitHub Releases page, downloads the latest setup installer,
and applies updates seamlessly.
"""

import os
import sys
import json
import hashlib
import urllib.request
import urllib.error
import subprocess
import ssl

REPO_OWNER = "ELISTE770"
REPO_NAME = "AIMemoryHub"
CURRENT_VERSION = "1.0.1"

GITHUB_API_LATEST = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases"
GITHUB_REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"

# Optional custom CA bundle for corporate/ISP TLS-inspecting proxies (e.g. NetFree).
# Set AIMEMORYHUB_CA_BUNDLE to the proxy's root certificate file instead of disabling
# certificate validation - an unverified connection would let any network attacker
# swap the downloaded installer for a malicious executable.
CA_BUNDLE_ENV = "AIMEMORYHUB_CA_BUNDLE"


def build_ssl_context() -> ssl.SSLContext:
    """
    Builds a *verifying* TLS context. If the user configured a custom CA bundle
    (for a TLS-inspecting proxy), it is loaded in addition to the system trust store,
    so certificate validation stays enabled in every case.
    """
    ctx = ssl.create_default_context()
    ca_bundle = os.environ.get(CA_BUNDLE_ENV, "").strip()
    if ca_bundle and os.path.exists(ca_bundle):
        try:
            ctx.load_verify_locations(cafile=ca_bundle)
        except Exception as e:
            print(f"[Updater] Failed to load custom CA bundle '{ca_bundle}': {e}")
    return ctx


def sha256_of_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    """Returns the lowercase hex SHA-256 digest of the file at path."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_asset_sha256(asset: dict | None) -> str | None:
    """
    Pulls the expected SHA-256 out of a GitHub release asset entry.
    GitHub exposes it as "digest": "sha256:<hex>" on newer API responses;
    returns None when the release doesn't publish one.
    """
    if not asset:
        return None
    digest = (asset.get("digest") or "").strip().lower()
    if digest.startswith("sha256:"):
        candidate = digest.split(":", 1)[1]
        if len(candidate) == 64:
            return candidate
    return None


def parse_version(v_str: str) -> tuple:
    """Parse version string like 'v6.2' or '6.2.1' into integer tuple for comparison."""
    if not v_str:
        return (0,)
    clean = v_str.strip().lstrip('vV')
    parts = []
    for segment in clean.split('.'):
        digits = ''.join(c for c in segment if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_for_updates(current_version: str = CURRENT_VERSION) -> tuple[bool, dict | None, str]:
    """
    Checks GitHub Releases for a newer version than current_version.
    Returns (update_available, release_info, message).
    """
    req = urllib.request.Request(
        GITHUB_API_LATEST,
        headers={
            "User-Agent": "AIMemoryHub-AutoUpdater",
            "Accept": "application/vnd.github.v3+json"
        }
    )

    data = None
    # 1. Try requests first if available (robust TLS negotiation)
    try:
        import requests
        resp = requests.get(
            GITHUB_API_LATEST,
            headers={
                "User-Agent": "AIMemoryHub-AutoUpdater",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
        elif resp.status_code == 404:
            return False, None, "טרם פורסמו שחרורים (Releases) במאגר זה."
        else:
            return False, None, f"שרת העדכונים החזיר קוד שגיאה: {resp.status_code}"
    except Exception:
        data = None

    # 2. Fallback to urllib if requests failed or was unavailable
    if data is None:
        try:
            ctx = build_ssl_context()
            with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
                if response.status != 200:
                    return False, None, f"שגיאת שרת העדכונים (HTTP {response.status})"
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, None, "טרם פורסמו שחרורים (Releases) במאגר זה."
            return False, None, f"שגיאת תקשורת מול שרת העדכונים (HTTP {e.code})"
        except ssl.SSLCertVerificationError as e:
            return False, None, (
                "אימות אישור האבטחה (TLS) נכשל. אם אתה מחובר דרך סינון/פרוקסי ארגוני, "
                f"הגדר את משתנה הסביבה {CA_BUNDLE_ENV} לנתיב אישור השורש שלו."
            )
        except Exception:
            return False, None, "לא ניתן לבדוק עדכונים כעת (שגיאת חיבור לרשת). אנא נסה שוב מאוחר יותר."

    tag_name = data.get("tag_name", "").strip()
    latest_ver = tag_name.lstrip("vV")
    latest_parsed = parse_version(latest_ver)
    current_parsed = parse_version(current_version)

    # Find download assets
    assets = data.get("assets", [])
    setup_asset = None
    portable_asset = None

    for a in assets:
        name = a.get("name", "").lower()
        if "setup" in name and name.endswith(".exe"):
            setup_asset = a
        elif name.endswith(".exe") and "setup" not in name:
            portable_asset = a

    release_info = {
        "tag_name": tag_name,
        "latest_version": latest_ver,
        "current_version": current_version,
        "title": data.get("name") or tag_name,
        "body": data.get("body") or "לא צוין פירוט שינויים לשחרור זה.",
        "html_url": data.get("html_url") or GITHUB_RELEASES_URL,
        "published_at": data.get("published_at", ""),
        "setup_download_url": setup_asset.get("browser_download_url") if setup_asset else None,
        "setup_size": setup_asset.get("size", 0) if setup_asset else 0,
        "setup_sha256": extract_asset_sha256(setup_asset),
        "portable_download_url": portable_asset.get("browser_download_url") if portable_asset else None,
        "portable_size": portable_asset.get("size", 0) if portable_asset else 0,
        "portable_sha256": extract_asset_sha256(portable_asset),
    }

    if latest_parsed > current_parsed:
        return True, release_info, f"נמצאה גרסה חדשה: {latest_ver}"
    else:
        return False, release_info, f"אתה משתמש בגרסה העדכנית ביותר ({current_version})"


def download_update(download_url: str, target_path: str, progress_callback=None, expected_sha256: str | None = None) -> tuple[bool, str]:
    """
    Downloads the update installer from download_url into target_path.
    Calls progress_callback(percent, downloaded_bytes, total_bytes) if provided.
    When expected_sha256 is supplied, the downloaded file is verified against it and
    deleted on mismatch, so a tampered installer is never left on disk to be executed.
    """
    if not download_url:
        return False, "לא נמצא נתיב הורדה תקין עבור קובץ ההתקנה."

    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "AIMemoryHub-AutoUpdater"}
        )

        ctx = build_ssl_context()
        with urllib.request.urlopen(req, timeout=120, context=ctx) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 1024 * 64  # 64 KB chunks

            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            with open(target_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        percent = (downloaded / total_size * 100) if total_size > 0 else 0
                        progress_callback(percent, downloaded, total_size)

        if expected_sha256:
            actual = sha256_of_file(target_path)
            if actual.lower() != expected_sha256.lower():
                try:
                    os.remove(target_path)
                except Exception:
                    pass
                return False, (
                    "אימות שלמות קובץ ההתקנה נכשל! הקובץ שהתקבל אינו תואם לחתימת השחרור הרשמית "
                    "ולכן נמחק. ייתכן שההורדה נפגמה או שגורם ברשת החליף את הקובץ."
                )

        return True, target_path
    except ssl.SSLCertVerificationError as e:
        return False, (
            "אימות אישור האבטחה (TLS) נכשל בעת ההורדה. אם אתה מחובר דרך סינון/פרוקסי ארגוני, "
            f"הגדר את משתנה הסביבה {CA_BUNDLE_ENV} לנתיב אישור השורש שלו. פרטים: {e}"
        )
    except Exception as e:
        return False, f"שגיאה בעת הורדת העדכון: {e}"


# Inno Setup flags for an unattended install. The installer is per-user
# (PrivilegesRequired=lowest + DefaultDirName={autopf}), so this runs without a UAC prompt.
SILENT_FLAGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]


def launch_installer_silent(setup_path: str, expected_sha256: str | None = None) -> tuple[bool, str]:
    """
    Starts the installer unattended and RETURNS - it does not kill the process.

    Meant to be called while the app is shutting down: by the time Inno Setup replaces the
    executable, the app has already closed its database and released the file, which is
    what makes a no-questions-asked update safe. The integrity check is repeated here and
    matters more than on the interactive path, because the download may have happened
    minutes earlier, leaving a wider window for the file to be swapped.
    """
    if not setup_path or not os.path.exists(setup_path):
        return False, "קובץ ההתקנה לא נמצא"

    if expected_sha256:
        try:
            actual = sha256_of_file(setup_path)
        except Exception as e:
            return False, f"אימות קובץ ההתקנה נכשל: {e}"
        if actual.lower() != expected_sha256.lower():
            try:
                os.remove(setup_path)
            except Exception:
                pass
            return False, "אימות שלמות קובץ ההתקנה נכשל - ההתקנה בוטלה"

    try:
        subprocess.Popen([setup_path] + SILENT_FLAGS, shell=False)
        return True, "ההתקנה השקטה הופעלה"
    except Exception as e:
        return False, f"לא ניתן להפעיל את המתקין: {e}"


def launch_installer_and_exit(setup_path: str, expected_sha256: str | None = None):
    """
    Executes the downloaded installer and terminates the current running process cleanly
    so that Inno Setup can overwrite the executable without file-locking errors.

    When expected_sha256 is supplied the file is re-hashed immediately before execution,
    closing the window in which another local process could swap the installer between
    the download finishing and this call (TOCTOU).
    """
    if not os.path.exists(setup_path):
        raise FileNotFoundError(f"Installer not found at {setup_path}")

    if expected_sha256:
        actual = sha256_of_file(setup_path)
        if actual.lower() != expected_sha256.lower():
            try:
                os.remove(setup_path)
            except Exception:
                pass
            raise ValueError("אימות שלמות קובץ ההתקנה נכשל - ההתקנה בוטלה מטעמי אבטחה.")

    # Launch installer in a detached process
    subprocess.Popen([setup_path], shell=False)
    # Immediately exit current python process
    os._exit(0)
