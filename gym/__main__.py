"""Command-line helpers: python -m gym {build,history,metrics,serve}."""
from __future__ import annotations

import argparse
import json
import sys

from . import build, report, session
from .metrics import analyze_transcript
from .workspace import Workspace


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gym")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="configure+build+test a session")
    b.add_argument("session", nargs="?", help="session id (default: latest)")
    b.add_argument("--preset", default="asan", choices=build.PRESETS)
    sub.add_parser("history", help="print progress table")
    sub.add_parser("sessions", help="list sessions")
    m = sub.add_parser("metrics", help="filler metrics for a text file, one answer per paragraph")
    m.add_argument("file")
    sub.add_parser("serve", help="run the MCP stdio server")
    a = p.parse_args(argv)
    ws = Workspace.from_env()

    if a.cmd == "serve":
        from .server import main as serve
        serve()
        return 0
    if a.cmd == "sessions":
        for s in session.list_sessions(ws):
            print(f"{s.id}\t{s.track}\t{s.difficulty}\t{s.status}\t{s.title}")
        return 0
    if a.cmd == "history":
        print(report.render_history_markdown(report.history(ws)))
        return 0
    if a.cmd == "metrics":
        text = open(a.file, encoding="utf-8").read()
        answers = [x for x in text.split("\n\n") if x.strip()]
        d = analyze_transcript(answers).to_dict()
        d.pop("per_answer")
        print(json.dumps(d, indent=2))
        return 0
    if a.cmd == "build":
        sid = a.session or (session.latest_session(ws).id if session.latest_session(ws) else None)
        if not sid:
            print("no sessions", file=sys.stderr)
            return 2
        s = build.build_and_test(ws, sid, a.preset)
        for st in s.steps:
            print(f"== {st.step}: rc={st.returncode} {st.duration_s}s")
            if not st.ok:
                print(st.output_tail)
        print(json.dumps(s.brief(), indent=2))
        return 0 if s.ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
