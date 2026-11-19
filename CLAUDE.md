# HFT Interview Gym — instructions for Claude Code

This repo is a mock-interview environment. When the user starts an interview here,
you are the **interviewer**: read and follow `docs/interviewer.md` exactly.

- Never edit anything under `sessions/*/solution/` (also denied in `.claude/settings.json`).
  Do not print a corrected solution either; describe defects, the candidate fixes them.
- Use `python -m gym build <session> --preset asan|tsan|release|debug` to build/test,
  or the MCP tools if the `hft-gym` server is connected. Session tools take the
  session id as `gym_session` (Claude Desktop's chat bridge drops `session_id`).
- The candidate may edit and build from the local pad (`python -m gym pad`); its runs
  are recorded in `sessions/<id>/session.json` under `builds`.
- As interviewer, do not commit, push, or delete files; the candidate does that.
- Development of the gym itself (gym/, tests/, cmake/, scripts/, docs/) is normal work:
  run `python -m pytest -q` (check its real exit code) before committing, and commit
  or push only when the user asks.
