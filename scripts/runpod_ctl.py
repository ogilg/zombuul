#!/usr/bin/env python3
"""RunPod pod management CLI. Used by Claude Code slash commands."""

import argparse
import functools
import os
import shlex
import subprocess
import sys
import time

import runpod
import yaml
from dotenv import load_dotenv

print = functools.partial(print, flush=True)

SSH_KEY = "~/.ssh/id_ed25519"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
USER_CONFIG = "~/.claude/zombuul.yaml"
VALID_CONFIG_KEYS = {"volume_gb", "disk_gb", "docker_image", "gpu_count", "cpu_instance_id", "python_version", "ssh_key", "template_id"}


def load_config() -> dict:
    shipped = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "defaults.yaml")
    with open(shipped) as f:
        config = yaml.safe_load(f)

    user_file = os.path.expanduser(USER_CONFIG)
    if os.path.exists(user_file):
        with open(user_file) as f:
            overrides = yaml.safe_load(f) or {}
        unknown = set(overrides) - VALID_CONFIG_KEYS
        if unknown:
            print(f"WARNING: Unknown keys in {user_file}: {', '.join(sorted(unknown))}")
        config.update(overrides)
    return config


def show_config():
    shipped = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "defaults.yaml")
    with open(shipped) as f:
        defaults = yaml.safe_load(f)

    user_file = os.path.expanduser(USER_CONFIG)
    user_overrides = {}
    if os.path.exists(user_file):
        with open(user_file) as f:
            user_overrides = yaml.safe_load(f) or {}
        print(f"Config: {user_file}")
    else:
        print(f"Config: defaults (no {USER_CONFIG})")

    config = dict(defaults)
    config.update(user_overrides)
    for k, v in sorted(config.items()):
        marker = " (user)" if k in user_overrides else ""
        print(f"  {k}: {v}{marker}")


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


def ssh_run(ip: str, port: int, command: str | list[str], **kwargs) -> subprocess.CompletedProcess:
    if isinstance(command, list):
        command = " ".join(shlex.quote(c) for c in command)
    return subprocess.run(ssh_cmd(ip, port) + [command], **kwargs)


# --- Pod info ---

def get_pod_env() -> dict[str, str]:
    """Collect tokens for the pod from environment, project .env, and ~/.claude/.env."""
    load_dotenv()  # load project .env into os.environ (no-op for already-set vars)
    load_dotenv(os.path.expanduser("~/.claude/.env"))  # global .env (no-op for already-set vars)
    return {k: v for k in ("HF_TOKEN", "GH_TOKEN", "SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID", "RUNPOD_API_KEY") if (v := os.environ.get(k))}


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


def setup_pod(ip: str, port: int, repo_url: str, branch: str, python_version: str = "3.12", install_claude: bool = False):
    setup_script = find_setup_script()

    print("  Copying pod_setup.sh...")
    scp_to_pod(ip, port, setup_script, "/pod_setup.sh")

    if install_claude:
        creds_file = extract_claude_credentials()
        if creds_file:
            print("  Copying Claude Code credentials...")
            ssh_run(ip, port, ["mkdir", "-p", "/root/.claude"], capture_output=True, text=True, check=True)
            scp_to_pod(ip, port, creds_file, "/root/.claude/.credentials.json")
        else:
            print("  WARNING: No Claude Code credentials found, skipping auth.")

    install_claude_flag = "true" if install_claude else "false"
    print(f"  Running pod_setup.sh in background (repo: {repo_url}, branch: {branch}, python: {python_version}, install_claude: {install_claude_flag})...")
    cmd = f"nohup bash /pod_setup.sh {shlex.quote(repo_url)} {shlex.quote(branch)} {shlex.quote(python_version)} {shlex.quote(install_claude_flag)} </dev/null > /var/log/pod_setup.log 2>&1 & disown"
    ssh_run(ip, port, cmd, capture_output=True, text=True)
    print("  Setup running. Check /var/log/pod_setup.log on the pod.")


# --- Commands ---

def list_gpus():
    gpus = runpod.get_gpus()
    for gpu in sorted(gpus, key=lambda g: g["memoryInGb"]):
        print(f"  {gpu['id']:45s} {gpu['memoryInGb']}GB")


def create_pod(name: str, gpu_type_id: str | None, image_name: str, repo_url: str, branch: str, *, python_version: str = "3.12", volume_gb: int = 100, disk_gb: int = 200, gpu_count: int = 1, cpu_instance_id: str = "cpu3c-2-4", template_id: str | None = None, install_claude: bool = False):
    kind = gpu_type_id or "CPU-only"
    if template_id:
        print(f"Creating pod '{name}' with {kind} (template: {template_id})...")
    else:
        print(f"Creating pod '{name}' with {kind}...")
    try:
        kwargs = dict(
            name=name,
            image_name=image_name,
            gpu_type_id=gpu_type_id,
            cloud_type="ALL",
            gpu_count=gpu_count if gpu_type_id else 0,
            volume_in_gb=volume_gb,
            container_disk_in_gb=disk_gb,
            volume_mount_path="/workspace",
            ports="8888/http,22/tcp",
            start_ssh=True,
            support_public_ip=True,
            env=get_pod_env(),
        )
        if template_id:
            kwargs["template_id"] = template_id
        if not gpu_type_id:
            kwargs["instance_id"] = cpu_instance_id
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
        return

    print(f"\nPod is ready!")
    print(f"  ID:  {pod_id}")
    print(f"  GPU: {kind}")
    print(f"  SSH: ssh root@{ip} -p {port} -i {SSH_KEY}")

    try:
        setup_pod(ip, port, repo_url, branch, python_version, install_claude=install_claude)
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


def pause_pod(pod_id: str):
    print(f"Pausing pod {pod_id}...")
    runpod.stop_pod(pod_id)
    print("Pod paused. GPU billing stopped.")
    print("Note: /workspace volume preserved; container disk (/, /opt/, /root/) is WIPED on resume.")
    print("If important experiment data lives on container disk, rsync it off-pod or to /workspace/ before pausing.")
    print("(Persistence is best-effort, not a guarantee — /workspace/ has its own pathologies.)")


def terminate_pod(pod_id: str, yes: bool = False):
    if not yes:
        print(f"ERROR: `terminate` destroys pod {pod_id} and all its disk contents.")
        print("Pass --yes to confirm.")
        sys.exit(2)
    print(f"Terminating pod {pod_id}...")
    runpod.terminate_pod(pod_id)
    print("Pod terminated. Disk destroyed; all billing stopped.")


def resume_pod(pod_id: str, gpu_count: int = 1):
    print(f"Resuming pod {pod_id} with gpu_count={gpu_count}...")
    if gpu_count == 0:
        print("  NOTE: RunPod's resume API with gpu_count=0 is known to return")
        print("        desiredStatus=RUNNING but boot the pod with vcpuCount=0,")
        print("        memoryInGb=0, and exit immediately. This is a RunPod-side")
        print("        limitation for GPU-reserved pods; CPU-only pods must be")
        print("        created fresh via `create --cpu`.")
    runpod.resume_pod(pod_id, gpu_count=gpu_count)
    print("Pod resume requested. Waiting for SSH...")
    ip, port = wait_for_ssh(pod_id)
    if ip:
        print(f"Pod is ready! SSH: ssh root@{ip} -p {port} -i {SSH_KEY}")
    else:
        print("Timed out waiting for pod. Check RunPod dashboard.")


def setup_status(pod_id: str):
    ip, port = get_ssh_info(pod_id)
    if not ip:
        print(f"Pod {pod_id} has no public SSH port.")
        return
    result = ssh_run(ip, port, ["tail", "-5", "/var/log/pod_setup.log"], capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"  Could not read setup log: {result.stderr.strip()}")


def wait_for_setup(pod_id: str, timeout: int = 900, poll_interval: int = 15):
    """Block until pod setup completes. Prints one-line progress updates."""
    ip, port = get_ssh_info(pod_id)
    if not ip:
        print(f"ERROR: Pod {pod_id} has no public SSH port.")
        sys.exit(1)

    start = time.time()
    last_line = ""
    while time.time() - start < timeout:
        done = ssh_run(
            ip, port, "grep -c 'Setup complete' /var/log/pod_setup.log",
            capture_output=True, text=True, timeout=120,
        )
        if done.returncode == 0 and done.stdout.strip() != "0":
            elapsed = int(time.time() - start)
            print(f"Setup complete ({elapsed}s)")
            return

        tail = ssh_run(
            ip, port, "tail -1 /var/log/pod_setup.log",
            capture_output=True, text=True, timeout=120,
        )
        if tail.returncode == 0:
            line = tail.stdout.strip()
            if line and line != last_line:
                last_line = line
                # Strip noisy progress lines (apt, pip, git file counts)
                if not any(noise in line for noise in ("Updating files:", "Reading package", "Building wheels", "Downloading", "Downloaded")):
                    print(f"  {line}")

        time.sleep(poll_interval)

    elapsed = int(time.time() - start)
    print(f"ERROR: Setup timed out after {elapsed}s")
    tail = ssh_run(
        ip, port, "tail -5 /var/log/pod_setup.log",
        capture_output=True, text=True, timeout=120,
    )
    if tail.returncode == 0:
        print(f"Last log lines:\n{tail.stdout.strip()}")
    sys.exit(1)


def main():
    global SSH_KEY
    config = load_config()
    SSH_KEY = config["ssh_key"]

    parser = argparse.ArgumentParser(description="RunPod management")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gpus", help="List available GPU types")
    sub.add_parser("list", help="List running pods")
    sub.add_parser("config", help="Show current effective config")

    create = sub.add_parser("create", help="Create a new pod")
    create.add_argument("--name", required=True)
    hw_group = create.add_mutually_exclusive_group(required=True)
    hw_group.add_argument("--gpu", help="GPU type ID")
    hw_group.add_argument("--cpu", action="store_true", help="Create a CPU-only pod (no GPU)")
    create.add_argument("--image", default=config["docker_image"], help=f"Docker image (default: from config)")
    create.add_argument("--repo-url", default=None, help="Git repo URL to clone on pod (default: current repo's origin)")
    create.add_argument("--branch", default=None, help="Git branch to checkout on pod (default: current branch)")
    create.add_argument("--python", default=config["python_version"], help=f"Python version for venv (default: from config)")
    create.add_argument("--gpu-count", type=int, default=config["gpu_count"], help=f"Number of GPUs (default: {config['gpu_count']})")
    create.add_argument("--volume-gb", type=int, default=config["volume_gb"], help=f"Volume size in GB (default: {config['volume_gb']})")
    create.add_argument("--disk-gb", type=int, default=config["disk_gb"], help=f"Disk size in GB (default: {config['disk_gb']})")
    create.add_argument("--template-id", default=config.get("template_id"), help="RunPod template ID (default: from config)")
    create.add_argument("--install-claude", action="store_true", help="Install Claude Code + zombuul plugin on the pod (for remote-mode experiments where the pod runs its own agent). Default off.")

    pause = sub.add_parser("pause", help="Pause a pod (stop GPU billing, keep disk)")
    pause.add_argument("pod_id")

    terminate = sub.add_parser("terminate", help="Destroy a pod (stops billing, deletes disk). Requires --yes.")
    terminate.add_argument("pod_id")
    terminate.add_argument("--yes", action="store_true", help="Confirm destruction (disk is deleted).")

    resume = sub.add_parser("resume", help="Resume a paused pod")
    resume.add_argument("pod_id")
    resume.add_argument("--gpu-count", type=int, default=1, help="Number of GPUs to resume with (default: 1). Passing 0 is accepted by the RunPod API but does not actually boot GPU-reserved pods — see `resume_pod` docstring.")

    status = sub.add_parser("status", help="Check setup progress on a pod")
    status.add_argument("pod_id")

    wait = sub.add_parser("wait-setup", help="Block until pod setup completes")
    wait.add_argument("pod_id")
    wait.add_argument("--timeout", type=int, default=900, help="Timeout in seconds (default: 900)")
    wait.add_argument("--poll-interval", type=int, default=15, help="Poll interval in seconds (default: 15)")

    args = parser.parse_args()

    if args.command == "config":
        show_config()
        return

    load_api_key()

    if args.command == "gpus":
        list_gpus()
    elif args.command == "list":
        list_pods()
    elif args.command == "create":
        repo_url = args.repo_url or get_repo_url()
        branch = args.branch or get_current_branch()
        gpu = None if args.cpu else args.gpu
        create_pod(
            args.name, gpu, args.image, repo_url, branch,
            python_version=args.python, volume_gb=args.volume_gb,
            disk_gb=args.disk_gb, gpu_count=args.gpu_count,
            cpu_instance_id=config["cpu_instance_id"],
            template_id=args.template_id,
            install_claude=args.install_claude,
        )
    elif args.command == "pause":
        pause_pod(args.pod_id)
    elif args.command == "terminate":
        terminate_pod(args.pod_id, yes=args.yes)
    elif args.command == "resume":
        resume_pod(args.pod_id, gpu_count=args.gpu_count)
    elif args.command == "status":
        setup_status(args.pod_id)
    elif args.command == "wait-setup":
        wait_for_setup(args.pod_id, timeout=args.timeout, poll_interval=args.poll_interval)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
