"""
When running as .exe run update to "lastest" github release upon launch.

Note: A running Windows .exe can't be overwritten, but it can be renamed. So on
startup the current .exe gets renamed and the fresh one is dropped in with the
proper name. We then relaunch from the new .exe

Note: Versioning is by file hash

There's 2 ways to update:
- self_update_if_needed() -> called when the app starts up
- is_stale()              -> called by /ensure_updated from pre-session checks
"""
# =============================================================================
# IMPORTANT!: THIS IS THE SELF-UPDATE MECHANISM. DO NOT CASUALLY EDIT.
# -----------------------------------------------------------------------------
# Every deployed local server relies on this file to pull new GH releases. If a
# change here breaks updating and that build gets published, those laptops can
# never auto-update again. Each one then has to be fixed by hand.
#
# If a broken version of the updater is shipped, and a student opens the app
# it will update. Once a rollback is created, the student will not be able to 
# roll back. Figuring out which students were affected will not be too difficult
# because the pre-session checks on the frontend block the session from starting
# if the localserver is out of date.
#
# =============================================================================
# vvvvvvvvvvvvvvvvvvvvvvvvvvvv DO NOT EDIT: START vvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.request

DEFAULT_RELEASES_URL = (
    "https://api.github.com/repos/drbiga/lsuadhd-local-server/releases/latest"
)

def _releases_url() -> str:
    return os.getenv("LSU_RELEASES_URL", DEFAULT_RELEASES_URL)


def _pick_asset(assets):
    """
    Retrieve the .exe asset from the github release.
    Note: if there's more than one .exe on the release, pick the one closest
    to the name of this exe; if nothing matches, pick the first one there
    """
    exes = []
    for asset in assets:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            exes.append(asset)

    if not exes: return None
    if len(exes) == 1: return exes[0]

    if getattr(sys, "frozen", False):
        mine = os.path.basename(sys.executable).lower()
    else:
        mine = None

    for asset in exes:
        if asset.get("name", "").lower() == mine:
            return asset
    return exes[0]


def _self_path():
    if getattr(sys, "frozen", False): return sys.executable
    return None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _latest_asset():
    """
    Returns (sha256_digest, download_url) for the latest release's asset, or
    None if it can't be determined
    """
    try:
        req = urllib.request.Request(
            _releases_url(),
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "lsuadhd-local-server"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            release = json.load(resp)
    except Exception as e:
        logging.warning("[updater] Could not reach GitHub (%s)", e)
        return None
    assets = release.get("assets", [])
    asset = _pick_asset(assets)
    if asset is None:
        logging.info("[updater] Latest release is missing an .exe file to update from")
        return None
    digest = asset.get("digest", "")
    digest = digest.removeprefix("sha256:")
    url = asset.get("browser_download_url")
    if not digest or not url: return None
    return digest, url


def _download(url: str, dest: str) -> None:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/octet-stream",
                 "User-Agent": "lsuadhd-local-server"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)


def is_stale() -> bool:
    exe = _self_path()
    if exe is None: return False
    latest = _latest_asset()
    if latest is None: return False
    digest = latest[0]
    return _sha256(exe) != digest


def self_update_if_needed() -> bool:
    """
    Runs once at startup. If a newer build is the latest release, replace this
    exe (using rename trick) and relaunch it.

    Returns True if it relaunched a new copyl; False to keep running the current exe.
    """
    exe = _self_path()
    if exe is None: return False  # running from source (likely for dev purposes), no update necessary
    if os.getenv("LSU_SKIP_UPDATE"):
        # The .env var above, when set =1, prevents updates from occuring
        # This is necessary for dev purposes when running a new version
        # of .exe without wanting an update.
        logging.info("[updater] LSU_SKIP_UPDATE set; skipping self-update")
        return False

    old = exe + ".old"

    logging.info("[updater] Checking for a newer build...")
    latest = _latest_asset()
    if latest is None:
        logging.info("[updater] No update available; running current build")
        return False
    digest = latest[0]
    url = latest[1]
    if _sha256(exe) == digest:
        logging.info("[updater] Already up to date")
        return False

    logging.info("[updater] New version found; downloading")
    new = exe + ".new"
    try:
        _download(url, new)
    except Exception as e:
        logging.warning("[updater] Download failed (%s); running current", e)
        if os.path.exists(new):
            os.remove(new)
        return False

    if _sha256(new) != digest:
        logging.error("[updater] Checksum mismatch; running current")
        os.remove(new)
        return False

    # rename trick
    try:
        if os.path.exists(old):
            os.remove(old)
        os.rename(exe, old)
        os.rename(new, exe)
    except OSError as e:
        logging.warning("[updater] Swap failed (%s); running current", e)
        return False

    logging.info("[updater] Updated; relaunching")
    subprocess.Popen([exe])
    return True


def current_build_id() -> str:
    exe = _self_path()
    if exe is None: return "source"
    return _sha256(exe)[:12]
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ DO NOT EDIT: END ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
