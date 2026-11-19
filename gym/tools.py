"""Plain-Python tool implementations exposed over MCP by gym.server.

Kept free of MCP imports so they can be unit-tested directly.
There is deliberately NO tool that writes into a session's solution/ directory,
deletes files, or runs git commands that modify the repository.
"""
from __future__ import annotations

from dataclasses import asdict

from . import __version__, build, gitview, report, session
from .workspace import Workspace

GUIDE_PATH = "docs/interviewer.md"


# MCP-facing tools take the session as `gym_session`, not `session_id`:
# Claude Desktop's chat bridge (mcp__remote-devices__*) drops an argument named
# `session_id` before it reaches the server (Stage 0, 2026-11-19), so every
# session tool failed with "session_id: Field required". Internal modules keep
# `session_id`; start_session returns both keys.


def _ws() -> Workspace:
    return Workspace.from_env()


def gym_ping() -> dict:
    """Health check. Returns the workspace root and server version."""
    ws = _ws()
    return {"ok": True, "version": __version__, "root": str(ws.root),
            "missing_build_tools": build.require_tools()}


def get_interviewer_guide() -> str:
    """Return the interviewer protocol. Call this at the start of every session."""
    return _ws().read_text(GUIDE_PATH)


def list_sessions() -> list[dict]:
    """List all interview sessions (id, title, track, difficulty, status)."""
    return [{k: v for k, v in asdict(s).items() if k != "builds"} for s in session.list_sessions(_ws())]


def start_session(slug: str, title: str, track: str, difficulty: str, problem_md: str) -> dict:
    """Create sessions/<date>-<slug>/ from the template and write problem.md.

    track: dsa|cpp|concurrency|low-latency|systems|networking|system-design
    difficulty: easy|medium|hard. problem_md must NOT contain the solution or hints.
    """
    st = session.create_session(_ws(), slug, title, track, difficulty, problem_md)
    return {"gym_session": st.id, "session_id": st.id, "path": f"sessions/{st.id}",
            "candidate_writes": f"sessions/{st.id}/solution/",
            "next": "write tests with write_scaffold_file(gym_session, 'tests/test_solution.cpp', ...)"}


def write_scaffold_file(gym_session: str, path: str, content: str, overwrite: bool = False) -> dict:
    """Write problem.md, notes.md, tests/** or bench/** inside a session.

    Writing to solution/** is refused: the candidate owns the solution.
    """
    p = _ws().interviewer_write(gym_session, path, content, overwrite)
    return {"written": p.relative_to(_ws().root).as_posix(), "bytes": len(content.encode())}


def read_file(path: str) -> str:
    """Read a text file under the workspace root (workspace-relative path)."""
    return _ws().read_text(path)


def list_files(path: str = "sessions") -> list[str]:
    """List files under a workspace directory (build/ and .git/ are skipped)."""
    return _ws().list_files(path)


def git_status() -> str:
    """Read-only `git status --short --branch`."""
    return gitview.status(_ws())


def git_diff(path: str = "sessions", staged: bool = False) -> str:
    """Read-only git diff for a path, plus a list of untracked files."""
    return gitview.diff(_ws(), path, staged)


def build_and_test(gym_session: str, preset: str = "asan") -> dict:
    """Configure, build and run tests. preset: asan (default) | tsan | release | debug."""
    return build.build_and_test(_ws(), gym_session, preset).to_dict()


def run_benchmark(gym_session: str, filter_regex: str = "") -> dict:
    """Build the release preset and run bench/ with Google Benchmark."""
    r = build.run_benchmark(_ws(), gym_session, filter_regex)
    return {"ok": r.ok, "returncode": r.returncode, "timed_out": r.timed_out,
            "duration_s": r.duration_s, "output": r.output_tail}


def set_session_status(gym_session: str, status: str) -> dict:
    """Update phase: setup|discussion|coding|review|done."""
    return {"status": session.set_status(_ws(), gym_session, status).status}


def save_transcript(gym_session: str, candidate_answers: list[str],
                    interviewer_questions: list[str] | None = None) -> dict:
    """Save the candidate's answers VERBATIM (keep uh/um, repetitions, errors) and
    return deterministic text metrics (fillers, hedges, answer length)."""
    return report.save_transcript(_ws(), gym_session, candidate_answers, interviewer_questions)


def save_report(gym_session: str, approach: str, technical: dict, communication: dict,
                verdict: str, strengths: list[str], weaknesses: list[str],
                weakness_notes: list[str], recommendations: list[str],
                rewrites: list[dict] | None = None) -> dict:
    """Write report.json + report.md and mark the session done.

    technical keys: correctness, complexity_analysis, cpp_knowledge, memory_management,
      concurrency, performance, code_quality, edge_cases (int 1-10 or null if N/A)
    communication keys: clarity, structure, vocabulary, grammar, conciseness,
      tradeoff_explanation (int 1-10)
    verdict: strong_no_hire|no_hire|lean_no_hire|lean_hire|hire|strong_hire
    weaknesses: kebab-case tags reused across sessions, e.g. 'rambling-answers'
    rewrites: [{"weak": "...", "stronger": "...", "why": "..."}]
    """
    r = report.Report(
        approach=approach, technical=technical, communication=communication, verdict=verdict,
        strengths=strengths, weaknesses=weaknesses, weakness_notes=weakness_notes,
        recommendations=recommendations,
        rewrites=[report.Rewrite(**x) for x in (rewrites or [])],
    )
    d = report.save_report(_ws(), gym_session, r)
    return {"saved": f"sessions/{gym_session}/report.md", "technical_mean": d["technical_mean"],
            "communication_mean": d["communication_mean"]}


def progress_history() -> dict:
    """All sessions with scores and recurring weakness tags (use to pick the next problem)."""
    return report.history(_ws())


ALL_TOOLS = (gym_ping, get_interviewer_guide, list_sessions, start_session, write_scaffold_file,
             read_file, list_files, git_status, git_diff, build_and_test, run_benchmark,
             set_session_status, save_transcript, save_report, progress_history)
