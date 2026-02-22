# வியூகம் · Viyugam

**A personal Life OS — text-only, Claude-powered.**

Viyugam (Tamil for "strategy/formation") is a command-line tool that acts as a personal life operating system. It helps you capture, plan, reflect, decide, and review — driven by AI, stored entirely on your machine.

---

## Install

```bash
bash install.sh
```

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The script installs both if needed and prompts for your Anthropic API key.

---

## Commands

| Command | What it does |
|---|---|
| `viyugam capture "thought"` | Add anything to your inbox |
| `viyugam plan` | Process inbox + build today's schedule |
| `viyugam done <id>` | Mark a task complete |
| `viyugam status` | Quick overview of today |
| `viyugam log` | Evening journal (conversational, AI-guided) |
| `viyugam think "proposal"` | Run a 3-voice boardroom debate on a decision |
| `viyugam think` | Review your someday list |
| `viyugam review` | Weekly / monthly / quarterly review |
| `viyugam goals` | List active goals |
| `viyugam goals --add "goal" --dimension career` | Add a goal |

---

## How it works

**Four cornerstones:**
- **Capture** — everything goes to inbox first, nothing is lost
- **Plan** — AI triages inbox and builds a time-blocked schedule from your context
- **Reflect** — conversational evening journal, derives dimension scores from the conversation
- **Review** — structured weekly/monthly/quarterly review (Reflect → Analyse → Intent)

**Six life dimensions:** health · wealth · career · relationships · joy · learning

**Seasons:** You declare a quarterly focus (intended season). Viyugam derives your actual season from your completed tasks. The gap between the two is the coaching insight.

**Resilience states:**
- `FLOW` — active in the last 48h
- `DRIFT` — 2–5 days inactive (gentle nudge)
- `BANKRUPTCY` — 5+ days (clean slate: archive overdue tasks, pause projects)

**Human Living Guardian:** When something involves the texture of human relationships — a friend's preferences, a personal memory, a gift idea — Viyugam pauses and asks if it should stay human rather than be tracked.

---

## Data

Everything lives in `~/.viyugam/`:

```
~/.viyugam/
  config.yaml          # your setup
  data/
    tasks.json
    projects.json
    goals.json
    inbox.json
    someday.json
    state.json
  journals/
    2025-01-15.md      # one markdown file per day
```

No cloud, no database, no accounts. Your data stays on your machine.

---

## Uninstall

```bash
bash uninstall.sh
```

Offers a backup of your data before removing anything.

---

## Tech

- Python 3.11+ · [uv](https://docs.astral.sh/uv/) for packaging
- [Claude Sonnet 4.6](https://anthropic.com) via the Anthropic API
- [Rich](https://github.com/Textualize/rich) for terminal formatting
- Local JSON + Markdown for storage
