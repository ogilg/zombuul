---
name: check-slack
description: Check the zombuul Slack channel for agent messages.
user-invocable: true
allowed-tools: Bash, AskUserQuestion
---

Fetch recent messages from Slack and act on them.

1. Run `curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" "https://slack.com/api/conversations.history?channel=$SLACK_CHANNEL_ID&limit=20"` and summarize what's new.
2. If any agent is asking for help or reporting an issue, decide whether you can help directly, need to escalate to the user, or if no action is needed.
3. To reply, post as `"username": "supervisor"` with icon `"icon_url": "https://dummyimage.com/48x48/3498DB/3498DB.png"`.
