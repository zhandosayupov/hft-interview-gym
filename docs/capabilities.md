# Claude capabilities relevant to this project (checked 2026-11-18)

Legend: **V** = verified in official Anthropic docs, **N** = news/third-party only,
**U** = unknown / not documented — must be tested on your machine (Stage 0).

| # | Capability | Status | Source / note |
|---|---|---|---|
| 1 | Two-way voice mode in Claude Desktop, web, mobile; all plans incl. Free; beta | V | [support: Use voice mode](https://support.claude.com/en/articles/11101966-use-voice-mode). Windows is not named explicitly; "Claude Desktop" is. |
| 2 | Voice mode is hands-free by default (continuous listening, responds to natural pauses); push-to-talk optional; you can interrupt by speaking | V | same article |
| 3 | Voice is turn-based, not full duplex | N | [Engadget, 2026-07-23](https://www.engadget.com/2221938/claude-voice-mode-just-got-smarter/) |
| 4 | Voice transcript saved as text in chat history; audio not kept | V | support article |
| 5 | Connected tools (connectors: Gmail, Calendar, Slack…) work in voice mode "the same way as in text chat"; paid plans choose model (Sonnet/Opus); Fable not available in voice | V | support article |
| 6 | **Local MCP servers (claude_desktop_config.json) callable from voice mode** | **U** | Not mentioned anywhere. This is the critical assumption — Stage 0 tests it. |
| 7 | **"In Claude Cowork and Claude Code, dictation is available but voice mode isn't."** | V | support article. ⇒ No two-way voice inside Cowork or the Code tab. |
| 8 | Claude Code CLI `/voice`: speech-to-text only (no spoken replies), hold-Space or tap mode, 20 languages, claude.ai login required, local mic required, not in SSH/cloud sessions; in WSL needs WSLg (+ `sox libsox-fmt-pulse` if audio fails) | V | [code.claude.com/docs/en/voice-dictation](https://code.claude.com/docs/en/voice-dictation) |
| 9 | Claude Code Desktop (Code tab) can run a session inside WSL 2; use it when the repo lives in the distro FS. Plugins unavailable in WSL sessions | V | [code.claude.com/docs/en/desktop-wsl](https://code.claude.com/docs/en/desktop-wsl.md) |
| 10 | Computer use: research preview on macOS & Windows Desktop, **Pro/Max/Ultra only** (not Team/Enterprise); enabled in Settings; CLI computer use is macOS-only | V | [Cowork computer use](https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork), [desktop docs](https://code.claude.com/docs/en/desktop) |
| 11 | Cowork: paid plans (Pro, Max, Ultra, Team, Enterprise); reads/writes only folders you connect; tasks run in an isolated cloud environment, reaching local files via the Desktop app | V | [Get started with Cowork](https://support.claude.com/en/articles/13345190-get-started-with-cowork) |
| 12 | Voice usage counts toward normal plan limits; no documented session-length cap | V | support article |

## Conclusion

A single Claude session that has **two-way voice + Claude Code/Cowork + computer
use** does not exist today (row 7). The only candidate for "voice + workspace
awareness in one window" is: **Desktop chat in voice mode + a local MCP server**
that exposes the workspace (rows 1, 5, 6). Row 6 is undocumented, so it is the
first thing to test. Computer use is not needed: source files, `git diff` and
compiler/test output give the interviewer strictly better information than
screenshots, and computer use is not available inside voice mode anyway.

## Measurement limits (be honest about these)

- Filler counts depend on the speech-to-text engine. Many ASR systems drop
  "uh/um". Stage 0 checks whether Claude's transcript keeps them. If not,
  filler metrics are a lower bound and must be labelled as such.
- Pauses, speaking rate and pronunciation cannot be measured from the text
  transcript. The tools do not pretend to.
- For calibration only: in conversational English, Bortfeld et al. (2001,
  *Language and Speech* 44(2)) report roughly 6 disfluencies per 100 words
  (all types, not only uh/um). Treat it as a conversational baseline, not an
  interview target.
