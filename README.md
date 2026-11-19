# HFT Interview Gym

[![ci](https://github.com/zhandosayupov/hft-interview-gym/actions/workflows/ci.yml/badge.svg)](https://github.com/zhandosayupov/hft-interview-gym/actions/workflows/ci.yml)

A Claude-run mock-interview environment for HFT C++ roles. Claude plays the
interviewer in English (voice and text), writes the problem and the tests,
watches your code through a sandboxed local MCP server, builds with
ASan/UBSan/TSan and saves a strict report. A local CoderPad-style page lets you
edit and run Build & Test yourself. **You write the solution; no tool can write
it for you.**

What Claude can and cannot do here, with sources and our own test results:
[`docs/capabilities.md`](docs/capabilities.md).

## How a session runs

Tested on Windows 10 + inbox WSL2 + Claude Desktop (Microsoft Store), 2026-11-19.
The hft-gym tools work in Claude Desktop **text** chat but are usually **not
available in voice mode** ([anthropics/claude-ai-mcp#661](https://github.com/anthropics/claude-ai-mcp/issues/661)),
so a session is a hybrid inside one project chat:

| Phase | Mode | What happens |
|---|---|---|
| 0. Setup | text | Interviewer creates the session and the tests; the problem stays hidden |
| 0.5. Introduction (5–8 min) | voice | About you, a performance-critical project, why HFT, one behavioural question |
| 1. Clarification & approach | voice | You ask questions, state approach and complexity before coding |
| 2. Coding | voice + **pad** | You code in the pad (or VS Code) and press Build & Test; runs are recorded |
| 3. Follow-ups | voice | Cache lines, memory order, allocation, benchmarking… |
| 4. Review & report | text | Final build, verbatim transcript, `report.md` with scores and rewrites |

The interviewer protocol ([`docs/interviewer.md`](docs/interviewer.md)) tells
Claude when to ask you to switch modes.

## Architecture

```
Windows                                    WSL2 Ubuntu (~/projects/hft-interview-gym)
┌──────────────────────────────┐   stdio   ┌─────────────────────────────────────────┐
│ Claude Desktop, Chat tab     │──wsl.exe──│ gym.server (MCP, Python)                │
│  project "HFT Interview"     │           │  ├ start_session / write_scaffold_file  │
│  text: tools · voice: talk   │           │  │   (problem.md, tests/, bench/ only)   │
└──────────────────────────────┘           │  ├ read_file / list_files / git_diff    │
┌──────────────────────────────┐   HTTP    │  ├ build_and_test / run_benchmark       │
│ Browser: localhost:8765      │──────────▶│ gym pad (candidate editor)              │
│  problem · editor · Build    │           │  └ writes solution/** only              │
└──────────────────────────────┘           │ save_transcript → metrics.json          │
┌──────────────────────────────┐           │ save_report / progress_history          │
│ VS Code (Remote - WSL), opt. │──edits───▶│ sessions/<id>/solution/                 │
└──────────────────────────────┘           └─────────────────────────────────────────┘
```

Why this shape:
- Two-way voice exists only in the Claude **chat** (Desktop/web/mobile), not in
  Cowork or Claude Code (they have dictation only).
- A local MCP server gives the chat file, git and build access, and lets the
  code itself enforce "the interviewer cannot touch `solution/`".
- The pad gives you a Build & Test button, so builds don't need the tools that
  voice mode lacks. Every run lands in `session.json`, where the interviewer reads it.
- Computer use is not used: files + `git diff` + compiler output are more
  reliable than screenshots, and it isn't available in voice mode.

## Repository layout

| Path | Purpose |
|---|---|
| `gym/` | Python package: sandbox policy, sessions, builds, metrics, reports, MCP server, pad |
| `gym/pad.py`, `gym/pad.html` | Local candidate pad (`python -m gym pad`) |
| `cmake/GymSession.cmake` | Shared flags: C++23, warnings, asan/tsan/release/debug, GoogleTest, Google Benchmark |
| `template/session/` | Copied for each session: `CMakeLists.txt`, `CMakePresets.json`, `solution/`, `tests/`, `bench/` |
| `sessions/<date>-<slug>/` | One interview: `problem.md`, your `solution/`, tests, `session.json`, `transcript.json`, `metrics.json`, `report.md/json` |
| `docs/interviewer.md` | Interviewer protocol, rubric, weakness tags, problem pool (served by `get_interviewer_guide`) |
| `docs/capabilities.md` | What Claude can/can't do here; Stage 0 results |
| `.claude/settings.json`, `CLAUDE.md` | Rules for Claude Code in this repo (edits to `solution/` denied) |
| `scripts/` | `setup-wsl.sh`, `check-env.sh`, `print-desktop-config.sh` |
| `tests/` | 100 pytest tests incl. real CMake/Ninja builds under GCC and Clang |

## Setup (Windows 10/11 + WSL2)

**Subscription.** Voice mode works on all plans; local tools, Opus in voice and
hour-long sessions need a paid plan (Pro is enough; Max if you hit limits).

1. **WSL2 + Ubuntu 24.04** (PowerShell as admin), then reboot:
   ```bash
   wsl --install -d Ubuntu-24.04
   ```
   The old inbox WSL (where `wsl --version` says "invalid option") works for
   everything here, including localhost forwarding for the pad.
2. **Clone** into the Linux filesystem (not `/mnt/c`):
   ```bash
   mkdir -p ~/projects && cd ~/projects && git clone https://github.com/zhandosayupov/hft-interview-gym && cd hft-interview-gym
   ```
3. **Install** (apt toolchain, venv, test suite; ends with `100 passed` and `Done.`):
   ```bash
   bash scripts/setup-wsl.sh
   ```
   If apt crawls at a few KiB/s, your route to `archive.ubuntu.com` is slow;
   point `/etc/apt/sources.list.d/ubuntu.sources` at a nearby mirror (keep a `.bak`).
4. **Verify** (read-only; compiles and runs tiny ASan/UBSan/TSan programs):
   ```bash
   bash scripts/check-env.sh
   ```
   `[opt]` lines (WSLg, sox) are only for the Claude Code `/voice` fallback.
5. **Connect Claude Desktop.** Print the entry and merge it into `mcpServers`:
   ```bash
   bash scripts/print-desktop-config.sh
   ```
   The config file is
   - standard installer: `%APPDATA%\Claude\claude_desktop_config.json`
   - Microsoft Store: `%LOCALAPPDATA%\Packages\AnthropicPBC.Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json`

   Then **fully quit** Claude Desktop (tray icon → Quit) and start it again.
   To check the server the way Desktop starts it, run in PowerShell:
   ```powershell
   wsl.exe -d Ubuntu --exec /home/<you>/projects/hft-interview-gym/.venv/bin/python -c "import gym.server; print('ok')"
   ```
6. **Claude Desktop → Chat → Projects → New project "HFT Interview"**, with these
   project instructions (in chat the tools are *deferred*; a keyword search for
   "hft-gym" can miss them, an exact-name select works):
   ```text
   You are the interviewer in my HFT mock interview.
   At the start of every chat, load the hft-gym tools by EXACT name (keyword
   search does not find them):
   select:mcp__remote-devices__hft-gym__gym_ping,mcp__remote-devices__hft-gym__get_interviewer_guide,mcp__remote-devices__hft-gym__start_session,mcp__remote-devices__hft-gym__set_session_status,mcp__remote-devices__hft-gym__write_scaffold_file,mcp__remote-devices__hft-gym__read_file,mcp__remote-devices__hft-gym__list_files,mcp__remote-devices__hft-gym__git_diff,mcp__remote-devices__hft-gym__build_and_test,mcp__remote-devices__hft-gym__run_benchmark,mcp__remote-devices__hft-gym__save_transcript,mcp__remote-devices__hft-gym__save_report,mcp__remote-devices__hft-gym__progress_history
   Then call get_interviewer_guide and follow it exactly.
   Never say the tools are unavailable before trying this exact select.
   Speak English. Never write or dictate my solution.
   ```
   Turn off unrelated connectors in this project so the interviewer stays on task.
7. **Optional: VS Code.** Install the **WSL** extension, run
   `code ~/projects/hft-interview-gym` from Ubuntu, then add **clangd** and
   **CMake Tools** in the WSL remote. Each session has its own `CMakePresets.json`
   and `compile_commands.json`.

## Running an interview

1. In WSL: `cd ~/projects/hft-interview-gym && source .venv/bin/activate && python -m gym pad`,
   then open <http://localhost:8765> in the Windows browser.
2. Claude Desktop → project "HFT Interview" → **new chat, text**:
   "Start an easy DSA interview." (or name a track: `cpp`, `concurrency`,
   `low-latency`, `systems`, `networking`, `system-design`; difficulty
   `easy`/`medium`/`hard`).
3. When setup is done, switch to **voice**: introduction, then the problem.
   Refer to tools in plain words ("build and test"), not snake_case names —
   speech-to-text mangles them.
4. Code in the pad, press **Build & Test** (Ctrl+Enter). Talk through it.
5. Switch back to **text** for review: "Build, save the transcript and write the report."
6. Commit the session (`git add sessions/<id> && git commit`). MCP tools never commit.

## Local pad (CoderPad-style)

`python -m gym pad` (inside WSL, from the repo root) serves <http://127.0.0.1:8765>:
problem on the left, C++ editor for `solution/` on the right (no autocomplete,
like a real interview pad), **Build & Test** buttons (ASan / TSan / Release), a
timer. Ctrl+S saves, Ctrl+Enter builds; files are saved before every build.
Every run is recorded in `session.json`, and the interviewer reads it.

Limits: the page writes **only** `solution/**` C++ sources (enforced in
`gym/workspace.py`); it binds 127.0.0.1, rejects foreign `Host`/`Origin`
headers and requires a custom header for writes and builds. The editor and the
Markdown renderer load from cdnjs; offline you get a plain text area. If you also
edit in VS Code, press **Reload** in the pad first.

## Stages

| Stage | What | Status / exit test |
|---|---|---|
| **0. Feasibility** | Text chat calls a tool; voice mode calls a tool; fillers survive transcription; no interruptions on pauses | **Done 2026-11-19**: text ✅, voice ❌ unreliable, fillers partly dropped (metrics are a lower bound), no interruptions. Details in `docs/capabilities.md`. |
| **1. Build loop** | `python -m gym build` / pad on a session; open it in VS Code | asan preset passes; clangd has no red squiggles. |
| **2. First full interview** (easy DSA) | "Start an easy DSA interview." Follow all phases | `report.md` exists with scores, rewrites, metrics. |
| **3. Concurrency** | Medium SPSC queue / seqlock with the `tsan` preset | TSan run recorded in `session.json`. |
| **4. Routine** | 3–4 sessions/week, mixed tracks; review `python -m gym history` | Recurring weakness tags shrink over 2–3 weeks. |
| **5. Optional** | Benchmarks (`run_benchmark`), system-design sessions (no code) | — |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Chat says the hft-gym tools are unavailable | They are deferred. Ask it to load them with the exact `select:` line from step 6. Check it is a chat **inside the project**, in the **Chat** tab (not Cowork). |
| Voice mode has no tools | Known Desktop bug ([#661](https://github.com/anthropics/claude-ai-mcp/issues/661)). Use the hybrid flow and the pad. |
| `session_id: Field required` | Old server. Session tools take `gym_session` (the chat bridge drops `session_id`). Pull, then fully quit and restart Desktop. |
| `mcp-server-hft-gym.log` shows no `tools/call` | Desktop does not log chat-originated calls there. To prove a call happened, watch the server process (`/proc/<pid>/io` write counter) or have Claude `read_file` a file with a random token. |
| Logs location | Standard install: `%APPDATA%\Claude\logs\`; Store: `%LOCALAPPDATA%\Packages\AnthropicPBC.Claude_*\LocalCache\Local\Claude\logs\` (`main.log`, `mcp.log`, `mcp-server-hft-gym.log`). |
| Pad page doesn't open from Windows | Check `curl http://localhost:8765/api/sessions` in PowerShell. If localhost isn't forwarded, run `python -m gym pad --host 0.0.0.0 --allow-host <WSL IP>` and open `http://<WSL IP>:8765`. |

## Fallback: no voice at all

Text chat in the project + OS dictation (Windows: **Win+H**): tools work, you
still speak; you read Claude's answers instead of hearing them. The Claude Code
CLI `/voice` route (`claude` in WSL) is dictation-only too and needs WSLg, which
the inbox WSL lacks; `CLAUDE.md` and `.claude/settings.json` keep the same rules there.

## Daily use

From the repo root with the venv active (`source .venv/bin/activate`):

```bash
python -m gym sessions          # list sessions
python -m gym pad               # CoderPad-style editor + Build & Test on http://127.0.0.1:8765
python -m gym build             # build + test latest session (asan)
python -m gym build <id> --preset tsan
python -m gym history           # progress table + recurring weaknesses
python -m pytest -q             # gym self-tests (add -m "not cpp" for the fast subset)
```

## Safety guarantees (and their limits)

- Enforced in code (`gym/workspace.py`, tested): paths resolved and confined to the
  repo (symlink escapes rejected); the interviewer writes only `problem.md`,
  `notes.md`, `tests/**`, `bench/**`; no overwrite without `overwrite=true`; no
  delete/commit/push tools; git access is `status/diff/log` only; build/test steps
  have timeouts that kill the whole process group (deadlocked tests can't hang the session).
- The pad is the candidate's editor: it writes only `solution/**` C++ sources and is
  never exposed through MCP; it is local-only (see above).
- Claude Code fallback: `Edit` deny rules cover Claude's file tools and recognised
  shell writes, but per Anthropic's docs they are **not** a hard boundary against
  arbitrary subprocesses. The MCP path is the stricter one.
