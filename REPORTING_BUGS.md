# Reporting zombuul bugs (for agents)

If during this session you hit friction in zombuul itself — failing pod setup, broken defaults, SSH/env quirks, silent crashes of zombuul scripts or skills, misleading error messages, missing features, monitoring gaps — file an issue before the session ends. **Do this even if you're running in someone else's repo** — the issue goes to the plugin, not the user's project.

## Scope

**In scope (file an issue):** `${CLAUDE_PLUGIN_ROOT}/scripts/`, the skills themselves, `defaults.yaml`, pod setup the plugin controls (`pod_setup.sh`, `launch_on_pod.sh`), `runpod_ctl.py`, babysit/monitor behavior, and documented workflows that don't work as documented.

**Out of scope (do not file):** bugs in the user's experiment code, missing deps the user's project expects, model-specific issues, one-off RunPod outages, anything specific to the user's own setup or environment.

## How

```
gh issue create --repo ogilg/zombuul \
  --title "<short>" \
  --body "<what happened + concrete command/error + suggested fix if obvious>"
```

Include:
- **What went wrong** (one or two sentences)
- **Concrete example** — the exact command, the error, and the context (which skill was invoking it, what pod type, what model)
- **Suggested fix** if obvious

## Conventions

- Batch multiple small papercuts from one session into a single issue rather than filing five separate ones.
- Before filing, skim recent open issues (`gh issue list --repo ogilg/zombuul --state open --limit 20`) and add a comment to an existing one instead of duplicating.
- Tell the user in one line that you're filing so they can override ("Filing a zombuul issue about the `.env` parse error — let me know if you'd rather I skip it.").
- Don't block on this — it's a reflection at session end or after hitting the bug, not during active work.
