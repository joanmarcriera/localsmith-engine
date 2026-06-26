# Unattended scheduler (macOS launchd)

The orchestrator can run itself on a timer via launchd. The plist lives in
[`launchd/com.marc.ai-workflow.plist`](../launchd/com.marc.ai-workflow.plist).
**Not installed yet** — install when you trust the pipeline enough to leave it alone.

## What it does

Every **30 minutes** (`StartInterval=1800`) launchd runs:

```bash
cd "/Users/marc/Development/Project/localsmith-engine"
shopt -s nullglob
bin/orchestrate.sh queue/*.md
```

`bin/orchestrate.sh` loads `.env` before running stages, so provider routing and
strict verification flags such as `REVIEW_PROVIDER=lmstudio` and
`VERIFY_DOCKER_BUILD=1` apply to scheduled runs as soon as they are set in `.env`.

The pipeline is idempotent end-to-end:

- `scaffold.sh` short-circuits when `projects/<slug>/tree.json` already exists.
- `state.py` tracks `current_step`; the orchestrator picks up wherever it left off.
- `impl.sh` skips files that already have non-zero size.
- `verify.sh` rewrites `report.md` and re-marks state — safe to re-run.

So a 30-minute tick on an already-complete project is a few stat calls and exits in
under a second.

## Install

```bash
cp launchd/com.marc.ai-workflow.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.marc.ai-workflow.plist
launchctl kickstart -k gui/$(id -u)/com.marc.ai-workflow   # force one run now (optional)
```

`bootstrap` registers the agent with launchd's GUI domain (so it can talk to network,
LM Studio, Ollama). `kickstart -k` triggers an immediate run regardless of the timer.

## Observe

Two log files written by launchd itself:

```bash
tail -f "logs/launchd.out" "logs/launchd.err"
```

Per-call token spend lives in `logs/tokens.jsonl`. Roll up daily:

```bash
awk -f bin/tokens.awk logs/tokens.jsonl
```

Local tool checks are also visible in the dashboard `/tools` page. It uses
`OLLAMA_HOST` for the LAN Ollama model inventory and `SEARXNG_HOST` for local search
grounding before cloud-model calls.

## Pause / resume / remove

```bash
# Pause without removing the agent
launchctl disable gui/$(id -u)/com.marc.ai-workflow

# Resume
launchctl enable  gui/$(id -u)/com.marc.ai-workflow

# Force one extra run right now
launchctl kickstart -k gui/$(id -u)/com.marc.ai-workflow

# Remove the agent entirely (does not delete the plist file from ~/Library/LaunchAgents)
launchctl bootout gui/$(id -u)/com.marc.ai-workflow
```

## Adjust the schedule

Edit `launchd/com.marc.ai-workflow.plist` then reload:

```bash
launchctl bootout   gui/$(id -u)/com.marc.ai-workflow
cp launchd/com.marc.ai-workflow.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.marc.ai-workflow.plist
```

Useful keys:

- `StartInterval` (seconds between runs). 1800 = every 30 min. Set to 3600 for hourly,
  300 for every 5 min during heavy testing.
- `StartCalendarInterval` (instead of `StartInterval`) for cron-style triggers like
  "every day at 06:00". Replace the `StartInterval` integer with a dict containing
  `Hour` and `Minute`.
- `RunAtLoad` (currently `false`). Set to `true` if you want a run the moment the agent
  is bootstrapped (i.e. on every login).
- `EnvironmentVariables` — currently sets `PATH` to include Homebrew. If your
  `claude`, `codex`, `uv`, or `ollama` clients live elsewhere, append their dirs.

## Anatomy of the plist

```xml
<key>Label</key>                <!-- unique launchctl identifier -->
<string>com.marc.ai-workflow</string>

<key>ProgramArguments</key>     <!-- argv, no shell parsing -->
<array>
    <string>/bin/bash</string>
    <string>-lc</string>        <!-- -l loads your login profile (PATH, etc.) -->
    <string>cd "/Users/marc/Development/Project/localsmith-engine" &amp;&amp; ...</string>
</array>

<key>WorkingDirectory</key>     <!-- safety; bash -c already does cd, but belt-and-braces -->
<string>/Users/marc/Development/Project/localsmith-engine</string>

<key>StandardOutPath</key>      <!-- launchd captures stdout/stderr here -->
<string>.../logs/launchd.out</string>
<key>StandardErrorPath</key>
<string>.../logs/launchd.err</string>
```

## Why launchd, not cron?

- `cron` on macOS is deprecated; launchd is the supported path.
- launchd persists across reboots without needing `@reboot`.
- Log capture is built in (`StandardOutPath` / `StandardErrorPath`).
- Pause/resume without editing the plist (`launchctl disable` / `enable`).

## Edge cases to know

- **Mac is asleep at tick time:** launchd queues the run for when the machine wakes,
  unless you explicitly want wake-from-sleep behaviour (different plist key, not set
  here intentionally — battery-friendly).
- **Network unreachable:** Ollama LAN box at 192.168.0.5 will time out, scaffold/verify
  will fail loud, state is preserved, next tick retries.
- **Two ticks overlap:** launchd serialises invocations of the same Label by default —
  a tick won't start if the previous one is still running. So `StartInterval=1800` is a
  floor, not a guarantee.
- **A project is stuck in `error`:** orchestrate.sh exits non-zero for that project and
  moves on to the next queue file. The error persists in `state.json["last_error"]`
  until a future run clears it.
