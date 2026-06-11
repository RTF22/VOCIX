"""Tests für vocix.updater."""

import hashlib
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from vocix import updater


class TestParseVersion:
    def test_with_v_prefix(self):
        assert updater._parse_version("v0.9.0") == (0, 9, 0, 1)

    def test_without_prefix(self):
        assert updater._parse_version("0.9.0") == (0, 9, 0, 1)

    def test_uppercase_v(self):
        assert updater._parse_version("V1.2.3") == (1, 2, 3, 1)

    def test_double_digit(self):
        assert updater._parse_version("v10.20.30") == (10, 20, 30, 1)

    def test_invalid_parts(self):
        with pytest.raises(ValueError):
            updater._parse_version("v1.2")

    def test_non_numeric(self):
        with pytest.raises(ValueError):
            updater._parse_version("va.b.c")

    def test_prerelease_parsed(self):
        v = updater._parse_version("1.4.0-beta.3")
        assert v == (1, 4, 0, 0, ((1, "beta"), (0, 3)))

    def test_prerelease_below_stable(self):
        """SemVer §11.3: 1.4.0-beta.3 < 1.4.0."""
        assert updater._parse_version("1.4.0-beta.3") < updater._parse_version("1.4.0")

    def test_prerelease_ordering(self):
        """SemVer §11.4: alpha < beta < rc; höhere Nummer > niedrigere."""
        assert updater._parse_version("1.0.0-alpha") < updater._parse_version("1.0.0-beta")
        assert updater._parse_version("1.0.0-beta.1") < updater._parse_version("1.0.0-beta.2")
        assert updater._parse_version("1.0.0-beta") < updater._parse_version("1.0.0-rc")

    def test_build_metadata_ignored(self):
        assert updater._parse_version("1.4.0+build.42") == (1, 4, 0, 1)

    def test_empty_prerelease_identifier(self):
        with pytest.raises(ValueError):
            updater._parse_version("1.0.0-beta.")


def _make_response(payload: dict):
    body = json.dumps(payload).encode("utf-8")

    class _Resp:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return body

    return _Resp()


class TestCheckLatest:
    def test_update_available(self):
        payload = {
            "tag_name": "v0.9.0",
            "html_url": "https://github.com/RTF22/VOCIX/releases/tag/v0.9.0",
            "body": "Notes",
        }
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            info = updater.check_latest("0.8.2", skip_version=None)
        assert info is not None
        assert info.version == "0.9.0"
        assert "v0.9.0" in info.url
        assert info.notes == "Notes"

    def test_same_version_returns_none(self):
        payload = {"tag_name": "v0.8.2", "html_url": "x", "body": ""}
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            assert updater.check_latest("0.8.2", skip_version=None) is None

    def test_older_release_returns_none(self):
        payload = {"tag_name": "v0.7.0", "html_url": "x", "body": ""}
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            assert updater.check_latest("0.8.2", skip_version=None) is None

    def test_skip_version_matches(self):
        payload = {"tag_name": "v0.9.0", "html_url": "x", "body": ""}
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            assert updater.check_latest("0.8.2", skip_version="0.9.0") is None

    def test_skip_version_with_v_prefix(self):
        payload = {"tag_name": "v0.9.0", "html_url": "x", "body": ""}
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            assert updater.check_latest("0.8.2", skip_version="v0.9.0") is None

    def test_skip_version_older_than_latest(self):
        """Skip gilt nur für exakte Match — neuere Releases zeigen trotzdem."""
        payload = {"tag_name": "v1.0.0", "html_url": "x", "body": ""}
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            info = updater.check_latest("0.8.2", skip_version="0.9.0")
        assert info is not None
        assert info.version == "1.0.0"

    def test_network_error_returns_none(self):
        from urllib.error import URLError
        with patch("vocix.updater.request.urlopen", side_effect=URLError("no net")):
            assert updater.check_latest("0.8.2", skip_version=None) is None

    def test_timeout_returns_none(self):
        with patch("vocix.updater.request.urlopen", side_effect=TimeoutError("timeout")):
            assert updater.check_latest("0.8.2", skip_version=None) is None

    def test_malformed_json_returns_none(self):
        class _BadResp:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                return b"{not json"
        with patch("vocix.updater.request.urlopen", return_value=_BadResp()):
            assert updater.check_latest("0.8.2", skip_version=None) is None

    def test_missing_tag_name_returns_none(self):
        with patch("vocix.updater.request.urlopen", return_value=_make_response({"body": "x"})):
            assert updater.check_latest("0.8.2", skip_version=None) is None

    def test_picks_asset_url_and_sha(self):
        payload = {
            "tag_name": "v0.9.0",
            "html_url": "x",
            "body": "",
            "assets": [
                {"name": "checksums.txt", "browser_download_url": "x", "digest": ""},
                {
                    "name": "VOCIX-v0.9.0-win-x64.zip",
                    "browser_download_url": "https://example/zip",
                    "digest": "sha256:" + ("a" * 64),
                },
            ],
        }
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            info = updater.check_latest("0.8.2", skip_version=None)
        assert info is not None
        assert info.asset_url == "https://example/zip"
        assert info.asset_name == "VOCIX-v0.9.0-win-x64.zip"
        assert info.sha256 == "a" * 64

    def test_beta_detects_stable_release(self):
        """Regression: 1.4.0-beta.3 muss v1.4.0 als Update sehen.

        Vorher schlug _parse_version('1.4.0-beta.3') mit ValueError fehl, der
        Update-Check schluckte den Fehler stillschweigend und meldete „aktuell".
        """
        payload = {"tag_name": "v1.4.0", "html_url": "x", "body": ""}
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            info = updater.check_latest("1.4.0-beta.3", skip_version=None)
        assert info is not None
        assert info.version == "1.4.0"

    def test_stable_does_not_offer_older_prerelease(self):
        payload = {"tag_name": "v1.4.0-beta.3", "html_url": "x", "body": ""}
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            assert updater.check_latest("1.4.0", skip_version=None) is None

    def test_no_matching_asset_keeps_url_empty(self):
        payload = {
            "tag_name": "v0.9.0",
            "html_url": "x",
            "body": "",
            "assets": [{"name": "other.zip", "browser_download_url": "x"}],
        }
        with patch("vocix.updater.request.urlopen", return_value=_make_response(payload)):
            info = updater.check_latest("0.8.2", skip_version=None)
        assert info is not None
        assert info.asset_url == ""


class TestVerifySha256:
    def test_match(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(b"hello")
        digest = hashlib.sha256(b"hello").hexdigest()
        assert updater.verify_sha256(f, digest) is True

    def test_mismatch(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(b"hello")
        assert updater.verify_sha256(f, "0" * 64) is False

    def test_empty_expected_skips(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(b"hello")
        assert updater.verify_sha256(f, None) is True
        assert updater.verify_sha256(f, "") is True


class TestExtractPayload:
    def test_extracts_inner_vocix_dir(self, tmp_path):
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("VOCIX/foo.txt", "bar")
            zf.writestr("VOCIX/sub/baz.txt", "qux")
        out = tmp_path / "extracted"
        result = updater._extract_payload(zip_path, out)
        assert result == out / "VOCIX"
        assert (result / "foo.txt").read_text() == "bar"
        assert (result / "sub" / "baz.txt").read_text() == "qux"

    def test_extracts_flat_zip(self, tmp_path):
        zip_path = tmp_path / "flat.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("foo.txt", "bar")
        out = tmp_path / "extracted"
        result = updater._extract_payload(zip_path, out)
        assert result == out
        assert (out / "foo.txt").read_text() == "bar"


class TestInstallUpdateGuards:
    def test_refuses_when_not_frozen(self, monkeypatch):
        monkeypatch.setattr(updater, "is_frozen_bundle", lambda: False)
        info = updater.UpdateInfo(version="9.9.9", url="", notes="", asset_url="x")
        with pytest.raises(RuntimeError, match="PyInstaller"):
            updater.install_update(info)

    def test_writes_helper_batch(self, monkeypatch, tmp_path):
        """End-to-end ohne tatsächliches Spawn — verifiziert Batch-Inhalt."""
        zip_path = tmp_path / "VOCIX-v0.9.0-win-x64.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("VOCIX/marker.txt", "ok")

        info = updater.UpdateInfo(
            version="0.9.0",
            url="x",
            notes="",
            asset_url="https://example/zip",
            asset_name="VOCIX-v0.9.0-win-x64.zip",
            sha256=None,
        )

        monkeypatch.setattr(updater, "is_frozen_bundle", lambda: True)
        target = tmp_path / "install"
        target.mkdir()

        def fake_download(info_, dest, progress_cb=None):
            dest.mkdir(parents=True, exist_ok=True)
            copy = dest / info_.asset_name
            copy.write_bytes(zip_path.read_bytes())
            return copy

        monkeypatch.setattr(updater, "download_asset", fake_download)
        monkeypatch.setattr(updater, "_spawn_detached", lambda p: None)

        batch = updater.install_update(info, target_dir=target, exe_name="VOCIX.exe")
        assert batch.exists()
        content = batch.read_text(encoding="ascii")
        assert "VOCIX.exe" in content
        assert str(target) in content
