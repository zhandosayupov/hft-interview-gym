import json

import pytest

from gym import report, session

from .conftest import PROBLEM

TECH = {k: 7 for k in report.TECH_DIMENSIONS} | {"concurrency": None}
COMM = {k: 5 for k in report.COMM_DIMENSIONS}


def make_report(**kw):
    base = dict(approach="Two pointers.", technical=dict(TECH), communication=dict(COMM),
                verdict="lean_hire", strengths=["fast"], weaknesses=["filler-words"],
                weakness_notes=["um x12"], recommendations=["practice"],
                rewrites=[report.Rewrite("Uh I think maybe heap", "A min-heap of size K: O(n log K).", "lead with answer")])
    base.update(kw)
    return report.Report(**base)


def test_mean_score_ignores_null():
    assert report.mean_score({"a": 6, "b": None, "c": 8}) == 7.0
    assert report.mean_score({"a": None}) is None


@pytest.mark.parametrize("field,value", [
    ("technical", {**TECH, "correctness": 11}),
    ("technical", {**TECH, "correctness": 0}),
    ("technical", {**TECH, "correctness": 7.5}),
    ("technical", {**TECH, "correctness": True}),
    ("technical", {**TECH, "bogus": 5}),
    ("technical", {k: v for k, v in TECH.items() if k != "correctness"}),
    ("communication", {**COMM, "clarity": None}),
    ("verdict", "maybe"),
    ("weaknesses", ["Filler Words"]),
    ("approach", "  "),
])
def test_validation_rejects(field, value):
    with pytest.raises(ValueError):
        report.validate_report(make_report(**{field: value}))


def test_save_transcript_and_report(ws, session_id):
    m = report.save_transcript(ws, session_id, ["Um, uh, I'd use a hash map.", "It's O(1) amortized."])
    assert m["filled_pauses_total"] == 2
    sdir = ws.session_dir(session_id)
    assert json.loads((sdir / "transcript.json").read_text())["candidate_answers"][0].startswith("Um")
    (sdir / "solution" / "solution.hpp").write_text("int add(int a,int b){return a+b;}")
    d = report.save_report(ws, session_id, make_report())
    assert d["technical_mean"] == 7.0 and d["communication_mean"] == 5.0
    assert d["transcript_metrics"]["answers"] == 2
    assert "solution.hpp" in d["solution_files"]
    md = (sdir / "report.md").read_text()
    assert "lean_hire" in md and "Stronger:" in md and "per 100 words" in md
    assert session.load_state(ws, session_id).status == "done"


def test_report_without_transcript_or_build(ws, session_id):
    d = report.save_report(ws, session_id, make_report(rewrites=[]))
    assert d["transcript_metrics"] is None and d["last_build"] is None
    assert "No build recorded" in (ws.session_dir(session_id) / "report.md").read_text()


def test_history_recurring_weaknesses(ws):
    from datetime import datetime, timezone
    ids = []
    for i, tags in enumerate([["filler-words", "hedging"], ["filler-words"], ["off-by-one"]]):
        st = session.create_session(ws, f"p{i}", f"P{i}", "dsa", "easy", PROBLEM,
                                    now=datetime(2026, 11, 18, 9, i, tzinfo=timezone.utc))
        report.save_report(ws, st.id, make_report(weaknesses=tags))
        ids.append(st.id)
    session.create_session(ws, "open", "Open", "cpp", "hard", PROBLEM,
                           now=datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc))
    h = report.history(ws)
    assert h["recurring_weaknesses"] == [("filler-words", 2)]
    assert len(h["sessions"]) == 4 and h["tracks_done"] == {"dsa": 3}
    md = report.render_history_markdown(h)
    assert "filler-words` × 2" in md and "(setup)" in md
