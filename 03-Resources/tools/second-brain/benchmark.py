#!/usr/bin/env python3
"""
benchmark.py — measure retrieval quality, so "did that change help?" has an answer.

Runs a fixed set of probe queries against the index and reports, per probe, the top-k
scores and the corpus median. Probes are declared in a JSON file, not in the code, so
each vault supplies queries that mean something in *its* content.

The headline number is **separation**:

    separation = (mean best score across `signal` probes)
               - (mean best score across `noise` probes)

`noise` probes are the control. They are gibberish or nonsense-but-well-formed input
that SHOULD score low. If a noise probe scores near a real question, retrieval is
matching structure rather than meaning, and every other number is decoration. This is
not hypothetical: on a title-only index, keyboard mash can score above the relevance
floor, because notes in one vault share a heading vocabulary (Findings / Impact /
Decision) and that is most of what such an index sees.

Reads the chunk index built by `embed_chunks.py`; falls back to the legacy title-only
store so an old index can still be measured for comparison.

⚠️ This hits Ollama, so it is NOT part of `tests/` (see CONTRIBUTING § Tests, "No
network, ever"). The pure functions it is built from are unit-tested in
`tests/test_benchmark.py`.

Usage:
  python3 benchmark.py                                  # run with probes.json, print a table
  python3 benchmark.py --save baseline.json             # run and record a baseline
  python3 benchmark.py --compare baseline.json          # run and show the delta vs a baseline
  python3 benchmark.py --probes my-probes.json --top 10
  python3 benchmark.py --legacy                         # measure the title-only store instead
  python3 benchmark.py --json                           # machine-readable

Probe file format:
  {
    "probes": [
      {"label": "exact title", "query": "second-brain",          "kind": "signal"},
      {"label": "keyboard mash","query": "asdfgh qwerty zxcvb",   "kind": "noise"}
    ]
  }
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DEFAULT_TOP_K,
    default_db_path,
    retrieve,
    retrieve_chunks,
)

DEFAULT_PROBES = Path(__file__).resolve().parent / "probes.json"  # copy probes.example.json
VALID_KINDS = ("signal", "noise")


# --- pure functions (unit-tested; no I/O, no network) ----------------------


def load_probes(data: dict) -> list[dict]:
    """Validate a probe document. Raises ValueError with a usable message.

    A benchmark with no noise probes cannot compute separation, which is the whole
    point, so that is an error rather than a warning.
    """
    if not isinstance(data, dict) or "probes" not in data:
        raise ValueError("probe file must be an object with a 'probes' key")
    probes = data["probes"]
    if not isinstance(probes, list) or not probes:
        raise ValueError("'probes' must be a non-empty list")
    for i, p in enumerate(probes):
        for field in ("label", "query", "kind"):
            if field not in p:
                raise ValueError(f"probe {i} is missing '{field}'")
        if p["kind"] not in VALID_KINDS:
            raise ValueError(f"probe {i} kind must be one of {VALID_KINDS}, got {p['kind']!r}")
        if not str(p["query"]).strip():
            raise ValueError(f"probe {i} has an empty query")
    if not any(p["kind"] == "noise" for p in probes):
        raise ValueError("at least one 'noise' probe is required — it is the control "
                         "that proves the index measures meaning, not structure")
    return probes


def summarise(label: str, kind: str, scores: list[float]) -> dict:
    """Per-probe summary. An empty result set is a real outcome, not an error."""
    return {
        "label": label,
        "kind": kind,
        "hits": len(scores),
        "best": round(max(scores), 3) if scores else 0.0,
        "mean": round(statistics.fmean(scores), 3) if scores else 0.0,
        "scores": [round(s, 3) for s in scores],
    }


def separation(rows: list[dict]) -> float | None:
    """Mean best `signal` score minus mean best `noise` score.

    Returns None when either class is absent. Higher is better; at or below zero the
    index cannot tell a real question from gibberish.
    """
    sig = [r["best"] for r in rows if r["kind"] == "signal"]
    noise = [r["best"] for r in rows if r["kind"] == "noise"]
    if not sig or not noise:
        return None
    return round(statistics.fmean(sig) - statistics.fmean(noise), 3)


def compare(current: list[dict], baseline: list[dict]) -> list[dict]:
    """Join two runs on probe label and compute deltas. Unmatched labels are kept."""
    base = {r["label"]: r for r in baseline}
    out = []
    for r in current:
        b = base.get(r["label"])
        out.append({
            "label": r["label"],
            "kind": r["kind"],
            "best": r["best"],
            "baseline": b["best"] if b else None,
            "delta": round(r["best"] - b["best"], 3) if b else None,
        })
    return out


def format_table(rows: list[dict]) -> str:
    """Fixed-width table of per-probe results."""
    w = max((len(r["label"]) for r in rows), default=5) + 2
    out = [f"{'probe':<{w}}{'kind':<9}{'best':>7}{'mean':>8}{'hits':>7}   top scores",
           "-" * (w + 40)]
    for r in rows:
        top = ", ".join(f"{s:.3f}" for s in r["scores"][:5])
        out.append(f"{r['label']:<{w}}{r['kind']:<9}{r['best']:>7.3f}"
                   f"{r['mean']:>8.3f}{r['hits']:>7}   {top}")
    return "\n".join(out)


def format_comparison(rows: list[dict]) -> str:
    w = max((len(r["label"]) for r in rows), default=5) + 2
    out = [f"{'probe':<{w}}{'kind':<9}{'baseline':>10}{'current':>9}{'delta':>9}",
           "-" * (w + 37)]
    for r in rows:
        if r["baseline"] is None:
            out.append(f"{r['label']:<{w}}{r['kind']:<9}{'—':>10}{r['best']:>9.3f}{'new':>9}")
            continue
        arrow = "+" if r["delta"] > 0 else ""
        out.append(f"{r['label']:<{w}}{r['kind']:<9}{r['baseline']:>10.3f}"
                   f"{r['best']:>9.3f}{arrow + format(r['delta'], '.3f'):>9}")
    return "\n".join(out)


def verdict(sep: float | None, base_sep: float | None = None) -> str:
    """One line a human can act on."""
    if sep is None:
        return "separation: n/a (need both signal and noise probes)"
    line = f"separation: {sep:+.3f}"
    if sep <= 0:
        line += "  🔴 noise scores as high as real questions — retrieval is matching structure, not meaning"
    elif sep < 0.10:
        line += "  ⚠️  weak — real questions barely outrank gibberish"
    else:
        line += "  ✅ real questions clearly outrank gibberish"
    if base_sep is not None:
        d = sep - base_sep
        line += f"   (baseline {base_sep:+.3f}, {'+' if d >= 0 else ''}{d:.3f})"
    return line


# --- I/O -------------------------------------------------------------------


def run_probes(db_path: Path, probes: list[dict], top_k: int, legacy: bool) -> list[dict]:
    rows = []
    for p in probes:
        fn = retrieve if legacy else retrieve_chunks
        hits = fn(db_path, p["query"], top_k=top_k, min_score=0.0)
        rows.append(summarise(p["label"], p["kind"], [h["score"] for h in hits]))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure retrieval quality against a fixed set of probe queries")
    parser.add_argument("--probes", type=Path, default=DEFAULT_PROBES,
                        help=f"Probe JSON file (default: {DEFAULT_PROBES.name})")
    parser.add_argument("--db", type=Path, default=None, help="Index path")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_K,
                        help=f"Results per probe (default: {DEFAULT_TOP_K})")
    parser.add_argument("--legacy", action="store_true",
                        help="Measure the title-only store instead of the chunk store")
    parser.add_argument("--save", type=Path, help="Write this run to a baseline file")
    parser.add_argument("--compare", type=Path, help="Show the delta against a baseline file")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Machine-readable output")
    args = parser.parse_args()

    db_path = args.db or default_db_path()
    if not db_path.exists():
        print(f"Index not found: {db_path}", file=sys.stderr)
        sys.exit(1)
    if not args.probes.exists():
        print(f"Probe file not found: {args.probes}", file=sys.stderr)
        sys.exit(1)

    try:
        probes = load_probes(json.loads(args.probes.read_text()))
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Bad probe file {args.probes}: {exc}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    rows = run_probes(db_path, probes, args.top, args.legacy)
    elapsed = time.time() - t0
    sep = separation(rows)

    payload = {
        "index": "legacy-title-only" if args.legacy else "chunked-body-text",
        "db": str(db_path),
        "probes": str(args.probes),
        "separation": sep,
        "elapsed_s": round(elapsed, 2),
        "rows": rows,
    }

    if args.compare:
        try:
            base = json.loads(args.compare.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Cannot read baseline {args.compare}: {exc}", file=sys.stderr)
            sys.exit(1)
        delta = compare(rows, base.get("rows", []))
        if args.as_json:
            print(json.dumps({**payload, "comparison": delta}, indent=2))
        else:
            print(format_comparison(delta))
            print()
            print(verdict(sep, base.get("separation")))
        return

    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(format_table(rows))
        print()
        print(verdict(sep))
        print(f"({payload['index']}, {len(probes)} probes, {elapsed:.1f}s)")

    if args.save:
        args.save.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"\nbaseline written: {args.save}", file=sys.stderr)


if __name__ == "__main__":
    main()
