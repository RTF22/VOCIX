"""Tests für vocix.updater."""

import io
import json
from unittest.mock import patch

import pytest

from vocix import updater


class TestParseVersion:
    def test_with_v_prefix(self):
        assert updater._parse_version("v0.9.0") == (0, 9, 0)

    def test_without_prefix(self):
        assert updater._parse_version("0.9.0") == (0, 9, 0)

    def test_uppercase_v(self):
        assert updater._parse_version("V1.2.3") == (1, 2, 3)

    def test_double_digit(self):
        assert updater._parse_version("v10.20.30") == (10, 20, 30)

    def test_invalid_parts(self):
        with pytest.raises(ValueError):
            updater._parse_version("v1.2")

    def test_non_numeric(self):
        with pytest.raises(ValueError):
            updater._parse_version("va.b.c")


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
