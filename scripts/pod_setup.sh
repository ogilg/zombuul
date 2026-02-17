#!/bin/bash
# Usage: bash pod_setup.sh <repo_url> [branch] [python_version]
# Generic pod bootstrap for zombuul research loops.
# Reads git identity and tokens from .env (SCP'd separately).

REPO_URL="${1:?Usage: bash pod_setup.sh <repo_url> [branch] [python_version]}"
BRANCH="${2:-main}"
PYTHON_VERSION="${3:-3.12}"
REPO_DIR="/workspace/repo"

# Import container env vars (not inherited when run via nohup over SSH)
if [ -f /proc/1/environ ]; then
    export $(cat /proc/1/environ | tr '\0' '\n' | grep -E '^(HF_TOKEN|GH_TOKEN)=')
fi

# System tools
apt-get update && apt-get install -y tmux jq
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && apt update && apt install gh -y

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

# Caches outside NFS to avoid per-user quota
export UV_CACHE_DIR=/opt/uv_cache
export HF_HOME=/opt/hf_cache
mkdir -p /opt/uv_cache /opt/hf_cache

# Python environment
pip install uv
mkdir -p /opt/venvs
rm -rf /opt/venvs/research
uv venv --python "$PYTHON_VERSION" /opt/venvs/research
source /opt/venvs/research/bin/activate
cd "$REPO_DIR"
uv pip install -e .
uv cache clean

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
    hf auth login --token $HF_TOKEN
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
source /opt/venvs/research/bin/activate
PROFILE

if [ -n "$HF_TOKEN" ]; then
    echo "export HF_TOKEN=$HF_TOKEN" >> ~/.bash_profile
fi
if [ -n "$GH_TOKEN" ]; then
    echo "export GH_TOKEN=$GH_TOKEN" >> ~/.bash_profile
fi

echo ""
echo "=== Setup complete ==="
