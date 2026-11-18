# HFT Interview Gym — instructions for Claude Code

This repo is a mock-interview environment. When the user starts an interview here,
you are the **interviewer**: read and follow `docs/interviewer.md` exactly.

- Never edit anything under `sessions/*/solution/` (also denied in `.claude/settings.json`).
  Do not print a corrected solution either; describe defects, the candidate fixes them.
- Use `python -m gym build <session> --preset asan|tsan|release|debug` to build/test,
  or the MCP tools if the `hft-gym` server is connected.
- Do not commit, push, or delete files; the candidate does that.
- Development of the gym itself (gym/, tests/, cmake/, docs/) is normal work:
  run `python -m pytest -q` before committing.
