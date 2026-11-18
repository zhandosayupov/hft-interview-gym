# HFT Interview Gym

A Claude-native mock-interview environment for HFT C++ roles: Claude runs a
spoken interview in English, writes the problem and tests, watches your code
through a sandboxed local MCP server, builds with ASan/UBSan/TSan, and saves a
strict report. **You write the solution; no tool can write it for you.**

See [`docs/capabilities.md`](docs/capabilities.md) for what Claude can and
cannot do here, with sources.

## Architecture (simplest thing that can work)

```
Windows                                   WSL2 Ubuntu (~/projects/hft-interview-gym)
┌─────────────────────────────┐   stdio   ┌──────────────────────────────────────┐
│ Claude Desktop              │──wsl.exe──│ gym.server (MCP, Python)             │
│  Project "HFT Interview"    │           │  ├ start_session / write_scaffold    │
│  chat in VOICE MODE         │           │  │   (problem.md, tests/, bench/ only)│
└─────────────────────────────┘           │  ├ read_file / list_files / git_diff │
┌─────────────────────────────┐           │  ├ build_and_test (cmake presets)    │
│ VS Code (Remote - WSL)      │──edits───▶│  ├ save_transcript → metrics.json    │
│  you write solution/        │           │  └ save_report / progress_history    │
└─────────────────────────────┘           └──────────────────────────────────────┘
```

Why this shape:
- Two-way voice exists only in the Claude **chat** (Desktop/web/mobile).
  Anthropic states voice mode is *not* available in Cowork or Claude Code.
- A local MCP server gives the voice chat file, git and build access, and
  lets the code itself enforce "the interviewer cannot touch `solution/`".
- Computer use is not used: it isn't available in voice chat, and files +
  `git diff` + compiler output are more reliable than screenshots.

**Unverified link:** Anthropic documents that *connectors* work in voice mode,
but does not say whether *local* MCP servers do. Stage 0 tests this. If it
fails, use the fallback below.

## Repository layout

| Path | Purpose |
|---|---|
| `gym/` | Python package: sandbox policy, sessions, builds, metrics, reports, MCP server |
| `cmake/GymSession.cmake` | Shared flags: C++23, warnings, asan/tsan/release/debug, GoogleTest, Google Benchmark |
| `template/session/` | Copied for each session: `CMakeLists.txt`, `CMakePresets.json`, `solution/`, `tests/`, `bench/` |
| `sessions/<date>-<slug>/` | One interview: `problem.md`, your `solution/`, tests, `transcript.json`, `metrics.json`, `report.md/json` |
| `docs/interviewer.md` | Interviewer protocol, rubric, weakness tags, problem pool (served by `get_interviewer_guide`) |
| `.claude/settings.json`, `CLAUDE.md` | Same rules for the Claude Code fallback (Edit on `solution/` denied) |
| `tests/` | 89 pytest tests incl. real CMake/Ninja builds under GCC and Clang |

## Setup (Windows 11 + WSL2)

**Subscription.** Voice mode works on all plans, but local tools, Opus in voice
and hour-long sessions need a paid plan; Pro is functionally enough. If you hit
usage limits in 60-minute sessions, move to Max. Computer use (not needed here)
requires Pro/Max/Ultra.

1. WSL2 + Ubuntu 24.04 (PowerShell as admin), then reboot:
   ```bash
   wsl --install -d Ubuntu-24.04
   ```
2. In Ubuntu, clone into the Linux filesystem (not `/mnt/c`):
   ```bash
   mkdir -p ~/projects && cd ~/projects && git clone <this repo> hft-interview-gym && cd hft-interview-gym
   ```
3. Read, then run, the installer (apt toolchain + venv + test suite):
   ```bash
   bash scripts/setup-wsl.sh
   ```
4. Verify (read-only; compiles and runs tiny ASan/UBSan/TSan programs):
   ```bash
   bash scripts/check-env.sh
   ```
5. Print the MCP entry and merge it into `%APPDATA%\Claude\claude_desktop_config.json`
   (Claude Desktop → Settings → Developer → Edit Config), then fully quit and restart Claude Desktop:
   ```bash
   bash scripts/print-desktop-config.sh
   ```
6. VS Code: install the **WSL** extension, then from Ubuntu run `code ~/projects/hft-interview-gym`.
   Install **clangd** and **CMake Tools** in the WSL remote. Each session folder has its own
   `CMakePresets.json` (asan / tsan / release / debug) and `compile_commands.json`.
7. Claude Desktop → Projects → New project "HFT Interview". Project instructions:
   ```text
   You are the interviewer in my HFT mock interview. At the start of every chat,
   call the hft-gym tool get_interviewer_guide and follow it exactly. Speak English.
   Never write or dictate my solution.
   ```

## Stages

Each stage has an exit test. Do not move on until it passes.

| Stage | What | Exit test |
|---|---|---|
| **0. Feasibility** (15 min) | (a) In a text chat in the project: "Call gym_ping." (b) Start voice mode, say: "Call gym ping and tell me the root path." (c) In voice, say literally: "Um, so, uh, I think, uh, a heap works." then stop and read the chat transcript. (d) Stay silent ~15 s mid-answer. | (a) returns the WSL path. (b) Claude calls the tool by voice → main design works; if not → fallback. (c) If "um/uh" are missing from the transcript, filler metrics are a lower bound only. (d) If Claude jumps in, switch voice to push-to-talk. |
| **1. Build loop** | `python -m gym build` on a hand-made session; open it in VS Code. | asan preset passes; clangd has no red squiggles. |
| **2. First full interview** (easy dsa) | Say: "Start an easy DSA interview." Follow all phases. | `report.md` exists with scores, rewrites, metrics. |
| **3. Concurrency** | Medium SPSC queue / seqlock with `tsan` preset. | TSan run recorded in `session.json`. |
| **4. Routine** | 3–4 sessions/week, mixed tracks; review `python -m gym history`. | Recurring weakness tags shrink over 2–3 weeks. |
| **5. Optional** | Benchmarks (`run_benchmark`), system-design sessions (no code), SQLite only if Markdown/JSON history gets painful. | — |

## Fallback if Stage 0(b) fails (voice cannot call local tools)

Run the interview in **Claude Code CLI inside WSL** from the repo root
(`claude`), with `/voice tap` for dictation. `CLAUDE.md` loads the same protocol;
`.claude/settings.json` denies edits to `solution/`. Trade-off: your speech is
transcribed, but Claude answers in text — you keep speaking practice, lose
listening practice. Do not run the discussion in a separate Desktop voice chat
unless you accept copying the transcript over manually.

## Daily use

```bash
python -m gym sessions          # list sessions
python -m gym build             # build + test latest session (asan)
python -m gym build <id> --preset tsan
python -m gym history           # progress table + recurring weaknesses
python -m pytest -q             # gym self-tests (add -m "not cpp" for the fast subset)
```

Commit your sessions yourself (`git add sessions/<id> && git commit`) — the
tools never commit, push or delete.

## Safety guarantees (and their limits)

- Enforced in code (`gym/workspace.py`, tested): paths resolved and confined to the
  repo (symlink escapes rejected); interviewer writes only `problem.md`, `notes.md`,
  `tests/**`, `bench/**`; no overwrite without `overwrite=true`; no delete/commit/push
  tools; git access is `status/diff/log` only; build/test steps have timeouts that
  kill the whole process group (deadlocked tests can't hang the session).
- Claude Code fallback: `Edit` deny rules cover Claude's file tools and recognised
  shell writes, but per Anthropic's docs they are **not** a hard boundary against
  arbitrary subprocesses. The MCP path is the stricter one.
