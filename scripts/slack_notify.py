#!/usr/bin/env python3
"""Post a message to Slack via incoming webhook."""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def notify(message: str):
    url = os.environ["SLACK_WEBHOOK_URL"]
    resp = requests.post(url, json={"text": message}, timeout=10)
    resp.raise_for_status()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python slack_notify.py 'your message'", file=sys.stderr)
        sys.exit(1)
    notify(" ".join(sys.argv[1:]))
