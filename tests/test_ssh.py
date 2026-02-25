"""Tests for ssh_run."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from runpod_ctl import ssh_run


class TestSshRun:
    def test_string_command(self):
        calls = []

        def capture(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

        with patch("runpod_ctl.subprocess.run", side_effect=capture):
            ssh_run("1.2.3.4", 22, "echo hello")
        assert calls[0][-1] == "echo hello"

    def test_list_command_is_quoted(self):
        calls = []

        def capture(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("runpod_ctl.subprocess.run", side_effect=capture):
            ssh_run("1.2.3.4", 22, ["echo", "hello world"])
        assert "echo 'hello world'" in calls[0][-1]

    def test_passes_kwargs(self):
        kwargs_seen = {}

        def capture(cmd, **kw):
            kwargs_seen.update(kw)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("runpod_ctl.subprocess.run", side_effect=capture):
            ssh_run("1.2.3.4", 22, "true", capture_output=True, text=True, timeout=10)
        assert kwargs_seen["capture_output"] is True
        assert kwargs_seen["text"] is True
        assert kwargs_seen["timeout"] == 10

    def test_returns_real_exit_code(self):
        def capture(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="err")

        with patch("runpod_ctl.subprocess.run", side_effect=capture):
            r = ssh_run("1.2.3.4", 22, "false", capture_output=True, text=True)
        assert r.returncode == 1

    def test_check_raises(self):
        def capture(cmd, **kw):
            if kw.get("check"):
                raise subprocess.CalledProcessError(1, cmd)
            return subprocess.CompletedProcess(cmd, 1)

        with patch("runpod_ctl.subprocess.run", side_effect=capture):
            try:
                ssh_run("1.2.3.4", 22, "false", check=True)
                assert False, "should have raised"
            except subprocess.CalledProcessError:
                pass
