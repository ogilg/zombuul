#!/bin/bash
# Usage: bash pod_setup.sh <repo_url> [branch]
# Generic pod bootstrap for zombuul research loops.
# Reads git identity and tokens from .env (SCP'd separately).

REPO_URL="${1:?Usage: bash pod_setup.sh <repo_url> [branch]}"
BRANCH="${2:-main}"
REPO_DIR="/workspace/repo"

# Import container env vars (not inherited when run via nohup over SSH)
if [ -f /proc/1/environ ]; then
    export $(cat /proc/1/environ | tr '\0' '\n' | grep -E '^(HF_TOKEN|GH_TOKEN)=')
fi

# System tools (must run as root)
apt-get update && apt-get install -y tmux sudo jq
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && apt update && apt install gh -y

# Create non-root user with persistent home in /workspace (survives pod restarts)
useradd -m -d /workspace/home/zombuul -s /bin/bash -u 1001 zombuul
echo "zombuul ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/zombuul
chown -R zombuul:zombuul /workspace

# Pass config to zombuul user script via files
echo "$REPO_URL" > /tmp/pod_repo_url
echo "$BRANCH" > /tmp/pod_branch

# Write zombuul user setup script (avoids heredoc variable expansion issues)
cat > /tmp/zombuul_setup.sh << 'ZOMBUUL_SCRIPT'
#!/bin/bash

REPO_URL="$(cat /tmp/pod_repo_url)"
BRANCH="$(cat /tmp/pod_branch)"
REPO_DIR="/workspace/repo"

# Clone repo and checkout branch
if [ ! -d "$REPO_DIR" ]; then
    git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"
git fetch origin
git checkout "$BRANCH"

# Claude Code
curl -fsSL https://claude.ai/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"

# Caches outside NFS home to avoid per-user quota
export UV_CACHE_DIR=/opt/uv_cache
export HF_HOME=/opt/hf_cache
sudo mkdir -p /opt/uv_cache /opt/hf_cache && sudo chown zombuul:zombuul /opt/uv_cache /opt/hf_cache

# Python environment (install outside /workspace to avoid NFS per-user quota)
pip install uv
sudo mkdir -p /opt/venvs && sudo chown zombuul:zombuul /opt/venvs
uv venv --python 3.12 /opt/venvs/zombuul
source /opt/venvs/zombuul/bin/activate
cd "$REPO_DIR"
uv pip install -e .

# Git config (from .env if present)
if [ -f "$REPO_DIR/.env" ]; then
    GIT_USER_NAME=$(grep '^GIT_USER_NAME=' "$REPO_DIR/.env" | cut -d= -f2-)
    GIT_USER_EMAIL=$(grep '^GIT_USER_EMAIL=' "$REPO_DIR/.env" | cut -d= -f2-)
fi
if [ -n "$GIT_USER_NAME" ]; then
    git config --global user.name "$GIT_USER_NAME"
fi
if [ -n "$GIT_USER_EMAIL" ]; then
    git config --global user.email "$GIT_USER_EMAIL"
fi

# Auth (tokens passed via environment)
if [ -n "$HF_TOKEN" ]; then
    huggingface-cli login --token $HF_TOKEN
    echo "Logged into Hugging Face."
fi

if [ -n "$GH_TOKEN" ]; then
    echo $GH_TOKEN | gh auth login --with-token
    echo "Logged into GitHub."
fi

# Write .bash_profile so login shells get venv + tokens
cat > ~/.bash_profile << 'PROFILE'
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR=/opt/uv_cache
export HF_HOME=/opt/hf_cache
source /opt/venvs/zombuul/bin/activate
PROFILE

if [ -n "$HF_TOKEN" ]; then
    echo "export HF_TOKEN=$HF_TOKEN" >> ~/.bash_profile
fi
if [ -n "$GH_TOKEN" ]; then
    echo "export GH_TOKEN=$GH_TOKEN" >> ~/.bash_profile
fi
ZOMBUUL_SCRIPT

chmod +x /tmp/zombuul_setup.sh

# Run as zombuul, forwarding tokens
su - zombuul -c "HF_TOKEN=$HF_TOKEN GH_TOKEN=$GH_TOKEN bash /tmp/zombuul_setup.sh"

# Claude Code auth: copy credentials from root to zombuul if present
if [ -f /root/.claude/.credentials.json ]; then
    mkdir -p /workspace/home/zombuul/.claude
    cp /root/.claude/.credentials.json /workspace/home/zombuul/.claude/.credentials.json
    chown -R zombuul:zombuul /workspace/home/zombuul/.claude
    chmod 600 /workspace/home/zombuul/.claude/.credentials.json
    echo "Claude Code credentials copied to zombuul user."
fi

echo ""
echo "=== Setup complete ==="
