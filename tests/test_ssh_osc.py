"""Tests for RunPod OSC escape stripping and exit code extraction."""

import sys
from pathlib import Path

# Add scripts/ to path so we can import runpod_ctl helpers
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from runpod_ctl import _strip_osc, _extract_exit_code, _RC_SENTINEL

OSC_PREFIX = "\x1b]11;#000000\x1b\\"


class TestStripOsc:
    def test_strips_osc_prefix(self):
        assert _strip_osc(f"{OSC_PREFIX}hello\n") == "hello\n"

    def test_strips_osc_from_middle(self):
        assert _strip_osc(f"before{OSC_PREFIX}after") == "beforeafter"

    def test_strips_multiple_osc(self):
        assert _strip_osc(f"{OSC_PREFIX}a{OSC_PREFIX}b") == "ab"

    def test_no_osc_unchanged(self):
        assert _strip_osc("hello world\n") == "hello world\n"

    def test_none_returns_none(self):
        assert _strip_osc(None) is None

    def test_empty_returns_empty(self):
        assert _strip_osc("") == ""

    def test_different_osc_color(self):
        assert _strip_osc("\x1b]11;#ffffff\x1b\\text") == "text"


class TestExtractExitCode:
    def test_success(self):
        stdout = f"hello\n{_RC_SENTINEL}0\n"
        cleaned, rc = _extract_exit_code(stdout)
        assert rc == 0
        assert cleaned == "hello\n"

    def test_failure(self):
        stdout = f"error msg\n{_RC_SENTINEL}1\n"
        cleaned, rc = _extract_exit_code(stdout)
        assert rc == 1
        assert cleaned == "error msg\n"

    def test_exit_code_2(self):
        stdout = f"{_RC_SENTINEL}2\n"
        cleaned, rc = _extract_exit_code(stdout)
        assert rc == 2
        assert cleaned == ""

    def test_multiline_output(self):
        stdout = f"line1\nline2\nline3\n{_RC_SENTINEL}0\n"
        cleaned, rc = _extract_exit_code(stdout)
        assert rc == 0
        assert cleaned == "line1\nline2\nline3\n"

    def test_no_sentinel(self):
        stdout = "just output\n"
        cleaned, rc = _extract_exit_code(stdout)
        assert rc is None
        assert cleaned == "just output\n"

    def test_sentinel_with_osc_already_stripped(self):
        raw = f"{OSC_PREFIX}output\n{_RC_SENTINEL}0\n"
        stripped = _strip_osc(raw)
        cleaned, rc = _extract_exit_code(stripped)
        assert rc == 0
        assert cleaned == "output\n"

    def test_high_exit_code(self):
        stdout = f"{_RC_SENTINEL}127\n"
        cleaned, rc = _extract_exit_code(stdout)
        assert rc == 127

    def test_empty_output_with_sentinel(self):
        stdout = f"{_RC_SENTINEL}0\n"
        cleaned, rc = _extract_exit_code(stdout)
        assert rc == 0
        assert cleaned == ""
