# Claude capabilities relevant to this project (checked 2026-11-18)

Legend: **V** = verified in official Anthropic docs, **N** = news/third-party only,
**U** = unknown / not documented — must be tested on your machine (Stage 0),
**T** = tested on the author's machine (see "Stage 0 results" below).

| # | Capability | Status | Source / note |
|---|---|---|---|
| 1 | Two-way voice mode in Claude Desktop, web, mobile; all plans incl. Free; beta | V | [support: Use voice mode](https://support.claude.com/en/articles/11101966-use-voice-mode). Windows is not named explicitly; "Claude Desktop" is. |
| 2 | Voice mode is hands-free by default (continuous listening, responds to natural pauses); push-to-talk optional; you can interrupt by speaking | V | same article |
| 3 | Voice is turn-based, not full duplex | N | [Engadget, 2026-07-23](https://www.engadget.com/2221938/claude-voice-mode-just-got-smarter/) |
| 4 | Voice transcript saved as text in chat history; audio not kept | V | support article |
| 5 | Connected tools (connectors: Gmail, Calendar, Slack…) work in voice mode "the same way as in text chat"; paid plans choose model (Sonnet/Opus); Fable not available in voice | V | support article |
| 6 | **Local MCP servers (claude_desktop_config.json) callable from voice mode** | **T** | Not documented by Anthropic. Stage 0 on 2026-11-19: works in **text chat**; **unreliable in voice mode** (later voice calls had no hft-gym tools) — see "Stage 0 results". |
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

- Filler counts depend on the speech-to-text engine. **Stage 0 showed that
  Claude's voice transcript drops some fillers** ("um" and one of two "uh"
  were lost, see below). Filler metrics are therefore a **lower bound only**
  and must be labelled as such in every report.
- The same engine garbles technical words ("a heap" → "he bought",
  "gym ping" → "Jim Pink"). Word-level metrics (answer length, hedges) are
  approximate; check the transcript before scoring precision of wording.
- Pauses, speaking rate and pronunciation cannot be measured from the text
  transcript. The tools do not pretend to.
- For calibration only: in conversational English, Bortfeld et al. (2001,
  *Language and Speech* 44(2)) report roughly 6 disfluencies per 100 words
  (all types, not only uh/um). Treat it as a conversational baseline, not an
  interview target.

## Stage 0 results (2026-11-19, author's machine)

Setup: Windows 10, inbox WSL2 (kernel 5.10, no WSLg), Claude Desktop from the
Microsoft Store. For the Store build the config is
`%LOCALAPPDATA%\Packages\AnthropicPBC.Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json`
and logs are in `...\LocalCache\Local\Claude\logs\` (not `%APPDATA%\Claude`).

| Test | Result | Evidence |
|---|---|---|
| (a) text chat calls a tool | **pass** | `read_file` on a file holding a random 24-hex nonce returned the exact nonce; the server process read the file at that moment. hft-gym is **not** listed in the chat's "+" menu, but the model sees all 15 tools. |
| (b) voice mode calls a tool | **unreliable** | One request reached the server at 12:55 during a test believed to be voice mode (its write counter grew), but the mode was not confirmed — it may have been dictation. Later voice calls in the project repeatedly said the hft-gym tools were not offered, while text chats in the same project had them. The first try also failed on speech-to-text ("gym ping" → "Jim Pink"). |
| (c) fillers in transcript | **partly dropped** | Said "Um, so, uh, I think, uh, a heap works." → transcript "I think he bought uh, I think heap works heap, not he like." ⇒ filler metrics are a lower bound only. |
| (d) ~15 s silence mid-answer | **no interruption** | Hands-free mode is fine; push-to-talk not needed. |

Verdict: **text chat + local MCP works; voice mode + local MCP is not reliable.**
Run interviews as a hybrid in one project chat: voice for the discussion
phase (no tools needed; the voice transcript stays in the chat as text), then
continue in **text** for scaffolding, build/test, `save_transcript` and the
report. Not yet verified: that the tools come back in text after a voice call
in the same chat — if not, continue in a new text chat and paste the voice
transcript. Alternative: text chat with OS dictation (Windows: Win+H) — keeps
speaking practice, loses listening practice.

Practical notes:
- Desktop does **not** log chat-originated `tools/call` in
  `mcp-server-hft-gym.log` (only `initialize`/`tools/list`). To verify a call,
  watch the server process (`/proc/<pid>/io` write counter) or use a nonce file.
- In voice, refer to tools in plain words ("health check", "build and test"),
  not by their snake_case names.
- In chat the tools are deferred and named `mcp__remote-devices__hft-gym__<tool>`.
  A keyword search for "hft-gym" sometimes misses them; an exact-name select works.
- The chat bridge drops an argument named `session_id`, so session tools take
  `gym_session` instead (calling the server directly with `session_id` worked).
