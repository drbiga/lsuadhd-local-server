import hashlib

import updater

# ---------------- is_stale ----------------

def test_is_stale_source_run(monkeypatch):
    def fake_self_path():
        return None

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    assert updater.is_stale() is False
    assert updater.current_build_id() == "source"


def test_is_stale_offline(monkeypatch, tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"abc")

    def fake_self_path():
        return str(exe)

    def fake_latest_asset():
        return None

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    monkeypatch.setattr(updater, "_latest_asset", fake_latest_asset)
    assert updater.is_stale() is False


def test_is_stale_current(monkeypatch, tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"abc")

    def fake_self_path():
        return str(exe)

    def fake_latest_asset():
        return (updater._sha256(str(exe)), "http://x")

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    monkeypatch.setattr(updater, "_latest_asset", fake_latest_asset)
    assert updater.is_stale() is False


def test_is_stale_true(monkeypatch, tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"abc")

    def fake_self_path():
        return str(exe)

    def fake_latest_asset():
        return ("0" * 64, "http://x")

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    monkeypatch.setattr(updater, "_latest_asset", fake_latest_asset)
    assert updater.is_stale() is True


# ---------------- self_update_if_needed ----------------

def _no_relaunch(monkeypatch):
    calls = []

    def fake_popen(args, **kwargs):
        calls.append(args)

    monkeypatch.setattr(updater.subprocess, "Popen", fake_popen)
    return calls


def test_self_update_source_run(monkeypatch):
    def fake_self_path():
        return None

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    assert updater.self_update_if_needed() is False


def test_self_update_skipped_by_env(monkeypatch, tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"X")

    hits = []

    def fake_self_path():
        return str(exe)

    def fake_latest_asset():
        hits.append(1)

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    monkeypatch.setenv("LSU_SKIP_UPDATE", "1")
    monkeypatch.setattr(updater, "_latest_asset", fake_latest_asset)
    assert updater.self_update_if_needed() is False
    assert hits == []


def test_self_update_current_does_nothing(monkeypatch, tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"CURRENT")

    def fake_self_path():
        return str(exe)

    def fake_latest_asset():
        return (updater._sha256(str(exe)), "http://x")

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    monkeypatch.setattr(updater, "_latest_asset", fake_latest_asset)
    calls = _no_relaunch(monkeypatch)
    assert updater.self_update_if_needed() is False
    assert calls == []
    assert exe.read_bytes() == b"CURRENT"


def test_self_update_offline_fail_open(monkeypatch, tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"OLD")

    def fake_self_path():
        return str(exe)

    def fake_latest_asset():
        return None

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    monkeypatch.setattr(updater, "_latest_asset", fake_latest_asset)
    _no_relaunch(monkeypatch)
    assert updater.self_update_if_needed() is False
    assert exe.read_bytes() == b"OLD"


def test_self_update_stale_swaps_and_relaunches(monkeypatch, tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"OLD")
    new_bytes = b"NEW_VERSION_BYTES"
    digest = hashlib.sha256(new_bytes).hexdigest()

    def fake_self_path():
        return str(exe)

    def fake_latest_asset():
        return (digest, "http://x/app.exe")

    def fake_download(url, dest):
        with open(dest, "wb") as f:
            f.write(new_bytes)

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    monkeypatch.setattr(updater, "_latest_asset", fake_latest_asset)
    monkeypatch.setattr(updater, "_download", fake_download)
    calls = _no_relaunch(monkeypatch)

    assert updater.self_update_if_needed() is True
    assert exe.read_bytes() == new_bytes
    assert (tmp_path / "app.exe.old").exists()
    assert not (tmp_path / "app.exe.new").exists()
    assert calls == [[str(exe)]]


def test_self_update_checksum_mismatch_rejected(monkeypatch, tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"OLD")

    def fake_self_path():
        return str(exe)

    def fake_latest_asset():
        return ("0" * 64, "http://x/app.exe")

    def fake_download(url, dest):
        with open(dest, "wb") as f:
            f.write(b"CORRUPT")

    monkeypatch.setattr(updater, "_self_path", fake_self_path)
    monkeypatch.setattr(updater, "_latest_asset", fake_latest_asset)
    monkeypatch.setattr(updater, "_download", fake_download)
    calls = _no_relaunch(monkeypatch)

    assert updater.self_update_if_needed() is False
    assert exe.read_bytes() == b"OLD"
    assert not (tmp_path / "app.exe.new").exists()
    assert calls == []


# ---------------- _pick_asset ----------------

def test_pick_asset_any_exe_name():
    assets = [{"name": "server-v2.1.exe", "digest": "sha256:x", "browser_download_url": "u"}]
    assert updater._pick_asset(assets)["name"] == "server-v2.1.exe"


def test_pick_asset_ignores_non_exe():
    assets = [{"name": "notes.txt"}, {"name": "app.exe"}]
    assert updater._pick_asset(assets)["name"] == "app.exe"


def test_pick_asset_none_without_exe():
    assert updater._pick_asset([{"name": "readme.md"}]) is None
