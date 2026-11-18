"""Session reports (JSON + Markdown) and cross-session progress history."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .metrics import analyze_transcript
from .session import list_sessions, load_state, save_state
from .workspace import Workspace

TECH_DIMENSIONS = ("correctness", "complexity_analysis", "cpp_knowledge", "memory_management",
                   "concurrency", "performance", "code_quality", "edge_cases")
COMM_DIMENSIONS = ("clarity", "structure", "vocabulary", "grammar", "conciseness",
                   "tradeoff_explanation")
VERDICTS = ("strong_no_hire", "no_hire", "lean_no_hire", "lean_hire", "hire", "strong_hire")
SCORE_MIN, SCORE_MAX = 1, 10


@dataclass
class Rewrite:
    weak: str
    stronger: str
    why: str = ""


@dataclass
class Report:
    approach: str
    technical: dict[str, int | None]
    communication: dict[str, int]
    verdict: str
    strengths: list[str]
    weaknesses: list[str]          # short kebab-case tags, e.g. "no-complexity-upfront"
    weakness_notes: list[str]
    recommendations: list[str]
    rewrites: list[Rewrite] = field(default_factory=list)


def _validate_scores(scores: dict, dims: tuple[str, ...], allow_null: bool) -> dict:
    unknown = set(scores) - set(dims)
    if unknown:
        raise ValueError(f"unknown dimensions: {sorted(unknown)}; allowed: {dims}")
    missing = set(dims) - set(scores)
    if missing:
        raise ValueError(f"missing dimensions: {sorted(missing)} (use null if not applicable)")
    for k, v in scores.items():
        if v is None and allow_null:
            continue
        if not isinstance(v, int) or isinstance(v, bool) or not SCORE_MIN <= v <= SCORE_MAX:
            raise ValueError(f"{k}: score must be an int in [{SCORE_MIN},{SCORE_MAX}]")
    return scores


def mean_score(scores: dict) -> float | None:
    vals = [v for v in scores.values() if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def validate_report(r: Report) -> Report:
    _validate_scores(r.technical, TECH_DIMENSIONS, allow_null=True)
    _validate_scores(r.communication, COMM_DIMENSIONS, allow_null=False)
    if r.verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    for tag in r.weaknesses:
        if not tag or tag != tag.strip().lower() or " " in tag:
            raise ValueError(f"weakness tags must be kebab-case: {tag!r}")
    if not r.approach.strip():
        raise ValueError("approach must not be empty")
    return r


def save_transcript(ws: Workspace, session_id: str, candidate_answers: list[str],
                    interviewer_questions: list[str] | None = None) -> dict:
    sdir = ws.session_dir(session_id)
    data = {
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_answers": candidate_answers,
        "interviewer_questions": interviewer_questions or [],
    }
    (sdir / "transcript.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    metrics = analyze_transcript(candidate_answers).to_dict()
    (sdir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def solution_fingerprint(ws: Workspace, session_id: str) -> dict[str, str]:
    sol = ws.session_dir(session_id) / "solution"
    out = {}
    if sol.is_dir():
        for p in sorted(sol.rglob("*")):
            if p.is_file():
                out[p.relative_to(sol).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def save_report(ws: Workspace, session_id: str, report: Report) -> dict:
    validate_report(report)
    sdir = ws.session_dir(session_id)
    state = load_state(ws, session_id)
    metrics_path = sdir / "metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.is_file() else None
    data = {
        "session_id": session_id,
        "title": state.title,
        "track": state.track,
        "difficulty": state.difficulty,
        "created_at": state.created_at,
        "reported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "approach": report.approach,
        "technical": report.technical,
        "technical_mean": mean_score(report.technical),
        "communication": report.communication,
        "communication_mean": mean_score(report.communication),
        "verdict": report.verdict,
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "weakness_notes": report.weakness_notes,
        "recommendations": report.recommendations,
        "rewrites": [r.__dict__ for r in report.rewrites],
        "builds": state.builds,
        "last_build": state.builds[-1] if state.builds else None,
        "solution_files": solution_fingerprint(ws, session_id),
        "transcript_metrics": _metrics_summary(metrics),
    }
    (sdir / "report.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    (sdir / "report.md").write_text(render_markdown(data), encoding="utf-8")
    state.status = "done"
    save_state(ws, state)
    return data


def _metrics_summary(m: dict | None) -> dict | None:
    if not m:
        return None
    keys = ("answers", "total_words", "median_answer_words", "max_answer_words",
            "filled_per_100w", "discourse_per_100w", "hedges_per_100w", "repetitions_total",
            "top_fillers", "long_answers")
    return {k: m[k] for k in keys}


def _table(scores: dict) -> str:
    rows = ["| Dimension | Score |", "|---|---|"]
    rows += [f"| {k} | {'n/a' if v is None else v} |" for k, v in scores.items()]
    return "\n".join(rows)


def render_markdown(d: dict) -> str:
    lines = [
        f"# Interview report — {d['title']}",
        "",
        f"- Session: `{d['session_id']}`  ",
        f"- Track / difficulty: {d['track']} / {d['difficulty']}  ",
        f"- Verdict: **{d['verdict']}**  ",
        f"- Technical mean: **{d['technical_mean']}** / 10, Communication mean: "
        f"**{d['communication_mean']}** / 10",
        "",
        "## Approach",
        d["approach"],
        "",
        "## Technical",
        _table(d["technical"]),
        "",
        "## Communication",
        _table(d["communication"]),
        "",
    ]
    tm = d.get("transcript_metrics")
    if tm:
        lines += [
            "### Transcript metrics (text only; no timing)",
            f"- Answers: {tm['answers']}, words: {tm['total_words']}, median answer: "
            f"{tm['median_answer_words']} words, longest: {tm['max_answer_words']}",
            f"- Filled pauses (uh/um): {tm['filled_per_100w']} per 100 words",
            f"- Discourse fillers (basically/actually/you know/like,): {tm['discourse_per_100w']} per 100 words",
            f"- Hedges (I think/maybe/probably): {tm['hedges_per_100w']} per 100 words",
            f"- Immediate repetitions: {tm['repetitions_total']}",
            f"- Top fillers: {', '.join(f'{w}×{n}' for w, n in tm['top_fillers']) or 'none'}",
            "",
        ]
    lb = d.get("last_build")
    lines += ["## Build & tests"]
    if lb:
        lines.append(f"- Last run: preset `{lb['preset']}`, ok={lb['ok']}, tests "
                     f"{lb['tests_passed']}/{lb['tests_total']}, sanitizer reports: "
                     f"{lb['sanitizer_reports']}")
    else:
        lines.append("- No build recorded.")
    lines += ["", "## Strengths", *[f"- {s}" for s in d["strengths"]], "",
              "## Weaknesses", *[f"- `{t}`" for t in d["weaknesses"]],
              *[f"- {n}" for n in d["weakness_notes"]], "",
              "## Weak answer → stronger answer"]
    for r in d["rewrites"]:
        lines += [f"> **Weak:** {r['weak']}", ">", f"> **Stronger:** {r['stronger']}"]
        if r.get("why"):
            lines += [">", f"> _Why:_ {r['why']}"]
        lines.append("")
    lines += ["## Next session", *[f"- {s}" for s in d["recommendations"]], ""]
    return "\n".join(lines)


def history(ws: Workspace) -> dict:
    rows = []
    tags: Counter = Counter()
    for s in list_sessions(ws):
        rp = ws.sessions_dir / s.id / "report.json"
        if not rp.is_file():
            rows.append({"session_id": s.id, "title": s.title, "status": s.status})
            continue
        r = json.loads(rp.read_text(encoding="utf-8"))
        tags.update(r["weaknesses"])
        tm = r.get("transcript_metrics") or {}
        rows.append({
            "session_id": s.id, "title": s.title, "track": s.track,
            "difficulty": s.difficulty, "status": s.status, "verdict": r["verdict"],
            "technical_mean": r["technical_mean"],
            "communication_mean": r["communication_mean"],
            "filled_per_100w": tm.get("filled_per_100w"),
        })
    return {
        "sessions": rows,
        "recurring_weaknesses": [(t, n) for t, n in tags.most_common() if n >= 2],
        "all_weaknesses": tags.most_common(),
        "tracks_done": dict(Counter(r.get("track") for r in rows if r.get("verdict"))),
    }


def render_history_markdown(h: dict) -> str:
    lines = ["# Progress", "",
             "| Session | Track | Diff | Verdict | Tech | Comm | uh/um per 100w |",
             "|---|---|---|---|---|---|---|"]
    for r in h["sessions"]:
        if "verdict" not in r:
            lines.append(f"| {r['session_id']} | – | – | ({r['status']}) | – | – | – |")
            continue
        lines.append(f"| {r['session_id']} | {r['track']} | {r['difficulty']} | {r['verdict']} | "
                     f"{r['technical_mean']} | {r['communication_mean']} | {r['filled_per_100w']} |")
    lines += ["", "## Recurring weaknesses (≥2 sessions)"]
    lines += [f"- `{t}` × {n}" for t, n in h["recurring_weaknesses"]] or ["- none yet"]
    return "\n".join(lines) + "\n"
