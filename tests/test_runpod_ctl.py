"""Basic tests for runpod_ctl.py — CLI parsing and pure helpers."""

import subprocess
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, "scripts")
import runpod_ctl


def test_ssh_cmd_format():
    cmd = runpod_ctl.ssh_cmd("1.2.3.4", 22222)
    assert cmd[0] == "ssh"
    assert "root@1.2.3.4" in cmd
    assert "-p" in cmd
    assert "22222" in cmd[cmd.index("-p") + 1]


def test_get_pod_env_filters_correctly():
    with patch.dict("os.environ", {"HF_TOKEN": "hf_abc", "GH_TOKEN": "gh_xyz", "UNRELATED": "x"}):
        env = runpod_ctl.get_pod_env()
        assert env == {"HF_TOKEN": "hf_abc", "GH_TOKEN": "gh_xyz"}


def test_get_pod_env_missing_tokens():
    with patch.dict("os.environ", {"UNRELATED": "x"}, clear=True):
        env = runpod_ctl.get_pod_env()
        assert env == {}


def test_get_current_branch_fallback():
    with patch("subprocess.run", side_effect=Exception("no git")):
        assert runpod_ctl.get_current_branch() == "main"


def test_cli_help_exits_cleanly():
    with pytest.raises(SystemExit) as exc_info:
        runpod_ctl.main.__wrapped__ if hasattr(runpod_ctl.main, "__wrapped__") else None
        with patch("sys.argv", ["runpod_ctl.py", "--help"]):
            runpod_ctl.main()
    assert exc_info.value.code == 0


def test_cli_no_command_does_not_crash():
    """Running with no subcommand should print help, not crash."""
    with patch("sys.argv", ["runpod_ctl.py"]), \
         patch.object(runpod_ctl, "load_api_key"):
        # Should not raise
        runpod_ctl.main()


def test_find_setup_script():
    path = runpod_ctl.find_setup_script()
    assert path.endswith("pod_setup.sh")


def test_get_ssh_info_no_ports():
    mock_pod = {"runtime": {"ports": []}}
    with patch("runpod.get_pod", return_value=mock_pod):
        ip, port = runpod_ctl.get_ssh_info("fake-id")
        assert ip is None
        assert port is None


def test_get_ssh_info_with_ssh_port():
    mock_pod = {
        "runtime": {
            "ports": [
                {"privatePort": 22, "isIpPublic": True, "ip": "5.6.7.8", "publicPort": 43210},
                {"privatePort": 8888, "isIpPublic": True, "ip": "5.6.7.8", "publicPort": 8888},
            ]
        }
    }
    with patch("runpod.get_pod", return_value=mock_pod):
        ip, port = runpod_ctl.get_ssh_info("fake-id")
        assert ip == "5.6.7.8"
        assert port == 43210
