# X → Telegram Mirror (agent skill)

Agent skill + templates for **automatic X → Telegram channel mirroring** via GitHub Actions. Each end user scaffolds **their own repo** with **their own** X Developer API key and BotFather bot — nothing runs from this open-source repo directly.

## For humans

1. Open this repository in **Cursor** (or use an agent that can read the skill).
2. Ask: *"Set up X to Telegram autoshare using the skill"*.
3. The agent copies `templates/` into **your new GitHub repo** and walks you through:
   - [developer.x.com](https://developer.x.com) Bearer token
   - [@BotFather](https://t.me/BotFather) bot + channel admin
   - Four **GitHub Secrets on your repo** (not on this upstream repo)

## For agents

Read [SKILL.md](SKILL.md) and [reference.md](reference.md).

Templates: [templates/](templates/)

## What gets created (in the user's repo)

```
monitor.py
requirements.txt
.gitignore
.github/workflows/mirror.yml
state/last_seen.json   # written by Actions after first run
```
