#!/usr/bin/env python3
"""RunPod pod management CLI. Used by Claude Code slash commands."""

import argparse
import functools
import os
import re
import shlex
import subprocess
import sys
import time

import runpod
from dotenv import load_dotenv

print = functools.partial(print, flush=True)

SSH_KEY = "~/.ssh/id_ed25519"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]


def load_api_key():
    load_dotenv(os.path.expanduser("~/.claude/.env"))
    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        print("ERROR: RUNPOD_API_KEY not found. Add it to ~/.claude/.env")
        sys.exit(1)
    runpod.api_key = key


# --- SSH/SCP helpers ---

def ssh_cmd(ip: str, port: int) -> list[str]:
    return ["ssh", f"root@{ip}", "-p", str(port), "-i", os.path.expanduser(SSH_KEY)] + SSH_OPTS


def scp_to_pod(ip: str, port: int, local_path: str, remote_path: str):
    scp_opts = ["-o", "StrictHostKeyChecking=no", "-i", os.path.expanduser(SSH_KEY)]
    subprocess.run(
        ["scp", "-P", str(port)] + scp_opts + [local_path, f"root@{ip}:{remote_path}"],
        check=True,
    )


# RunPod containers inject an OSC 11 escape sequence (\x1b]11;#000000\x1b\\)
# on every SSH command's stdout, and SSH returns exit code 1 even when the
# remote command succeeds. This regex strips it from captured output.
_OSC_RE = re.compile(r"\x1b\]11;[^\x1b]*\x1b\\")


_RC_SENTINEL = "__ZOMBUUL_RC__"


def _strip_osc(text: str | None) -> str | None:
    if text is None:
        return None
    return _OSC_RE.sub("", text)


def _extract_exit_code(stdout: str) -> tuple[str, int | None]:
    """Extract real exit code from sentinel line, return (cleaned_stdout, exit_code)."""
    if _RC_SENTINEL not in stdout:
        return stdout, None
    lines = stdout.rstrip("\n").split("\n")
    exit_code = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith(_RC_SENTINEL):
            try:
                exit_code = int(lines[i][len(_RC_SENTINEL):])
            except ValueError:
                pass
            lines.pop(i)
            break
    cleaned = "\n".join(lines) + "\n" if lines else ""
    return cleaned, exit_code


def ssh_run(ip: str, port: int, command: str | list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command on a pod via SSH.

    Handles RunPod's OSC escape injection: strips escape sequences from
    captured output and recovers the real remote exit code (which RunPod's
    infrastructure masks by always returning 1).

    command can be a shell string or a list of argv tokens (will be shell-quoted).
    Always pass capture_output=True, text=True to get accurate exit codes.
    """
    caller_check = kwargs.pop("check", False)
    capture = kwargs.get("capture_output", False)
    text_mode = kwargs.get("text", False)

    if isinstance(command, str):
        cmd_str = command
    else:
        cmd_str = " ".join(shlex.quote(c) for c in command)
    wrapped = cmd_str + f"; echo {_RC_SENTINEL}$?"
    result = subprocess.run(ssh_cmd(ip, port) + [wrapped], **kwargs)

    if capture and text_mode:
        result.stdout = _strip_osc(result.stdout)
        result.stderr = _strip_osc(result.stderr)

        if result.stdout:
            result.stdout, real_rc = _extract_exit_code(result.stdout)
            if real_rc is not None:
                result.returncode = real_rc
    else:
        # Without capture we can't extract the real exit code.
        # Best effort: assume rc=1 is the RunPod artifact.
        if result.returncode == 1:
            result.returncode = 0

    if caller_check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

    return result


# --- Pod info ---

def get_pod_env() -> dict[str, str]:
    return {k: v for k in ("HF_TOKEN", "GH_TOKEN", "SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID") if (v := os.environ.get(k))}


def get_ssh_info(pod_id: str) -> tuple[str | None, int | None]:
    info = runpod.get_pod(pod_id)
    runtime = info.get("runtime")
    if runtime and runtime.get("ports"):
        for port in runtime["ports"]:
            if port["privatePort"] == 22 and port["isIpPublic"]:
                return port["ip"], port["publicPort"]
    return None, None


def wait_for_ssh(pod_id: str) -> tuple[str | None, int | None]:
    for _ in range(60):
        ip, port = get_ssh_info(pod_id)
        if ip:
            break
        info = runpod.get_pod(pod_id)
        status = info.get("desiredStatus", "UNKNOWN")
        print(f"  Status: {status}... waiting 10s")
        time.sleep(10)
    else:
        return None, None

    for attempt in range(12):
        result = ssh_run(ip, port, ["echo", "ok"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return ip, port
        print(f"  SSH not accepting connections yet... waiting 5s (attempt {attempt + 1}/12)")
        time.sleep(5)

    print("  WARNING: SSH port reported but not accepting connections.")
    return ip, port


# --- Setup steps ---

def get_current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "main"


def extract_claude_credentials() -> str | None:
    """Extract fresh Claude Code credentials from macOS Keychain. Returns path or None."""
    creds_file = os.path.expanduser("~/.claude/.credentials.json")
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            os.makedirs(os.path.dirname(creds_file), exist_ok=True)
            with open(creds_file, "w") as f:
                f.write(result.stdout.strip())
            os.chmod(creds_file, 0o600)
            print("  Extracted fresh credentials from Keychain.")
            return creds_file
    except Exception as e:
        print(f"  Could not extract from Keychain: {e}")

    if os.path.exists(creds_file):
        return creds_file
    return None


def find_setup_script() -> str:
    """Find pod_setup.sh next to this script."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pod_setup.sh")
    if not os.path.exists(path):
        print(f"ERROR: pod_setup.sh not found at {path}")
        sys.exit(1)
    return path


def get_repo_url() -> str:
    """Get the git remote URL of the current working directory."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    print("ERROR: Could not determine git remote URL. Pass --repo-url explicitly.")
    sys.exit(1)


def run_setup_remote(ip: str, port: int, repo_url: str, branch: str, python_version: str = "3.12"):
    setup_script = find_setup_script()

    print("  Copying pod_setup.sh...")
    scp_to_pod(ip, port, setup_script, "/pod_setup.sh")

    creds_file = extract_claude_credentials()
    if creds_file:
        print("  Copying Claude Code credentials...")
        ssh_run(ip, port, ["mkdir", "-p", "/root/.claude"], capture_output=True, text=True, check=True)
        scp_to_pod(ip, port, creds_file, "/root/.claude/.credentials.json")
    else:
        print("  WARNING: No Claude Code credentials found, skipping auth.")

    print(f"  Running pod_setup.sh in background (repo: {repo_url}, branch: {branch}, python: {python_version})...")
    ssh_run(
        ip, port,
        f"nohup bash /pod_setup.sh {shlex.quote(repo_url)} {shlex.quote(branch)} {shlex.quote(python_version)} > /var/log/pod_setup.log 2>&1 &",
        capture_output=True, text=True, check=True,
    )
    print("  Setup running. Check /var/log/pod_setup.log on the pod.")


# --- Commands ---

def list_gpus():
    gpus = runpod.get_gpus()
    for gpu in sorted(gpus, key=lambda g: g["memoryInGb"]):
        print(f"  {gpu['id']:45s} {gpu['memoryInGb']}GB")


CPU_INSTANCE_ID = "cpu3c-2-4"


def create_pod(name: str, gpu_type_id: str | None, image_name: str, repo_url: str, branch: str, python_version: str = "3.12", volume_gb: int = 100, disk_gb: int = 50):
    kind = gpu_type_id or "CPU-only"
    print(f"Creating pod '{name}' with {kind}...")
    try:
        kwargs = dict(
            name=name,
            image_name=image_name,
            gpu_type_id=gpu_type_id,
            cloud_type="ALL",
            gpu_count=1 if gpu_type_id else 0,
            volume_in_gb=volume_gb,
            container_disk_in_gb=disk_gb,
            volume_mount_path="/workspace",
            ports="8888/http,22/tcp",
            start_ssh=True,
            support_public_ip=True,
            env=get_pod_env(),
        )
        if not gpu_type_id:
            kwargs["instance_id"] = CPU_INSTANCE_ID
            kwargs["container_disk_in_gb"] = min(disk_gb, 20)
        pod = runpod.create_pod(**kwargs)
    except Exception as e:
        print(f"ERROR creating pod: {e}")
        sys.exit(1)

    pod_id = pod["id"]
    print(f"Pod created: {pod_id}")
    print("Waiting for SSH to be ready...")

    ip, port = wait_for_ssh(pod_id)
    if not ip:
        print(f"Timed out waiting for pod {pod_id}. Check RunPod dashboard.")
        print(f"Run: python {os.path.abspath(__file__)} stop " + pod_id)
        return

    print(f"\nPod is ready!")
    print(f"  ID:  {pod_id}")
    print(f"  GPU: {kind}")
    print(f"  SSH: ssh root@{ip} -p {port} -i {SSH_KEY}")

    try:
        run_setup_remote(ip, port, repo_url, branch, python_version)
    except Exception as e:
        print(f"  WARNING: Setup failed: {e}")
        print(f"  Pod is still running. SSH in and run setup manually.")


def list_pods():
    pods = runpod.get_pods()
    if not pods:
        print("No pods found.")
        return
    for pod in pods:
        status = pod.get("desiredStatus", "UNKNOWN")
        gpu = pod.get("machine", {}).get("gpuDisplayName", "?")
        print(f"  {pod['id']:25s} {pod['name']:30s} {status:10s} {gpu}")


def stop_pod(pod_id: str):
    print(f"Terminating pod {pod_id}...")
    runpod.terminate_pod(pod_id)
    print("Pod terminated.")


def setup_status(pod_id: str):
    ip, port = get_ssh_info(pod_id)
    if not ip:
        print(f"Pod {pod_id} has no public SSH port.")
        return
    result = ssh_run(ip, port, ["tail", "-5", "/var/log/pod_setup.log"], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"  Could not read setup log: {result.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(description="RunPod management")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gpus", help="List available GPU types")
    sub.add_parser("list", help="List running pods")

    create = sub.add_parser("create", help="Create a new pod")
    create.add_argument("--name", required=True)
    hw_group = create.add_mutually_exclusive_group(required=True)
    hw_group.add_argument("--gpu", help="GPU type ID")
    hw_group.add_argument("--cpu", action="store_true", help="Create a CPU-only pod (no GPU)")
    create.add_argument("--image", required=True)
    create.add_argument("--repo-url", default=None, help="Git repo URL to clone on pod (default: current repo's origin)")
    create.add_argument("--branch", default=None, help="Git branch to checkout on pod (default: current branch)")
    create.add_argument("--python", default="3.12", help="Python version for venv (default: 3.12)")
    create.add_argument("--volume-gb", type=int, default=50)
    create.add_argument("--disk-gb", type=int, default=200)

    stop = sub.add_parser("stop", help="Terminate a pod")
    stop.add_argument("pod_id")

    status = sub.add_parser("status", help="Check setup progress on a pod")
    status.add_argument("pod_id")

    args = parser.parse_args()

    load_api_key()

    if args.command == "gpus":
        list_gpus()
    elif args.command == "list":
        list_pods()
    elif args.command == "create":
        repo_url = args.repo_url or get_repo_url()
        branch = args.branch or get_current_branch()
        gpu = None if args.cpu else args.gpu
        create_pod(args.name, gpu, args.image, repo_url, branch, args.python, args.volume_gb, args.disk_gb)
    elif args.command == "stop":
        stop_pod(args.pod_id)
    elif args.command == "status":
        setup_status(args.pod_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
