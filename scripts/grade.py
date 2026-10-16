#!/usr/bin/env python3
"""Compute state report card grades from the published rubric and the state data files.

Usage:
  python3 scripts/grade.py --write           # recompute and write data/report_cards/grades/<version>.json
  python3 scripts/grade.py --check           # recompute and fail (exit 1) if the committed file differs
  python3 scripts/grade.py --state NJ        # print one state's card to stdout

The computation is deterministic: the output carries no timestamps, only a fingerprint of the input
files, so two runs over the same data produce byte-identical JSON. CI runs --check so that a grade on
the site can never differ from what the rubric and the data imply.

Inputs are named values derived from each state's files by the functions in DERIVED below. Every
derivation returns the value and the provenance blocks it rested on, so the card can show the source
and review status of each input. The rubric's scoring rows are evaluated in order with a small, closed
set of operators (see evaluate_when); the first matching row awards its points.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_DIR = DATA / "report_cards" / "grades"
SUBSTANTIVE_EXCLUDED = {"responsible_gambling_message_required"}


# ---------------------------------------------------------------- loading
def load_yaml(p: Path) -> Any:
    return yaml.safe_load(p.read_text())


def load_bundle(abbr_dir: Path, prevalence: dict) -> dict:
    profile = load_yaml(abbr_dir / "profile.yaml")
    pg_path = abbr_dir / "pg_funding.yaml"
    pg = load_yaml(pg_path) if pg_path.exists() else None
    fips = str(profile["fips"]).zfill(2)
    return {"profile": profile, "pg_funding": pg, "prevalence": [s for s in prevalence.get("studies", []) if str(s["fips"]).zfill(2) == fips]}


def prov_summary(block: dict | None) -> dict | None:
    if not block:
        return None
    return {k: block.get(k) for k in ("source_id", "source_url", "retrieved_at", "status")}


# ---------------------------------------------------------------- derived inputs
# Each function: bundle -> (value, [provenance blocks]). A None value means "not entered".
def d_market_live(b: dict):
    rows = [r for r in (b["profile"].get("legal_status") or []) if r.get("market_segment") == "regulated_sportsbook" and r.get("status") == "live"]
    return (bool(rows), [r.get("provenance") for r in rows])


def _cp(b: dict, key: str):
    cp = b["profile"].get("consumer_protections") or {}
    return cp.get(key)


def d_self_exclusion_program_type(b: dict):
    se = _cp(b, "self_exclusion")
    return (se["program_type"], [se.get("provenance")]) if se else (None, [])


def d_deposit_limits_entered(b: dict):
    dl = _cp(b, "deposit_limits")
    return (True, [dl.get("provenance")]) if dl else (None, [])


def d_deposit_mandatory_default(b: dict):
    dl = _cp(b, "deposit_limits")
    return (dl.get("mandatory_default"), [dl.get("provenance")]) if dl else (None, [])


def d_deposit_required_at_signup(b: dict):
    dl = _cp(b, "deposit_limits")
    return (dl.get("player_set_required_at_signup"), [dl.get("provenance")]) if dl else (None, [])


def d_deposit_player_set_available(b: dict):
    dl = _cp(b, "deposit_limits")
    return (dl.get("player_set_available"), [dl.get("provenance")]) if dl else (None, [])


def d_advertising_rule_count(b: dict):
    adv = _cp(b, "advertising")
    if adv is None:
        return (None, [])
    return (len(adv), [r.get("provenance") for r in adv])


def d_advertising_substantive_count(b: dict):
    adv = _cp(b, "advertising")
    if adv is None:
        return (None, [])
    rows = [r for r in adv if r.get("rule_type") not in SUBSTANTIVE_EXCLUDED]
    return (len(rows), [r.get("provenance") for r in rows])


def d_legal_age_min(b: dict):
    ages = b["profile"].get("legal_age") or []
    if not ages:
        return (None, [])
    return (min(int(a["age"]) for a in ages), [a.get("provenance") for a in ages])


def d_credit_card_allowed(b: dict):
    cc = _cp(b, "credit_card_deposits")
    return (cc.get("allowed"), [cc.get("provenance")]) if cc else (None, [])


def d_pg_funding_mechanism(b: dict):
    pg = b["pg_funding"]
    if not pg or not pg.get("records"):
        return (None, [])
    latest = sorted(pg["records"], key=lambda r: r["fiscal_year"])[-1]
    return (latest.get("funding_mechanism"), [latest.get("provenance")])


def d_prevalence_searched(b: dict):
    # The prevalence file is a national list; a state with no study on file has been searched as part of the
    # Phase 2 pass only once its profile is full. Status-only profiles have not been searched.
    full = b["profile"].get("profile_completeness") == "full"
    return (True if (full or b["prevalence"]) else None, [])


def d_prevalence_years_since_latest(b: dict, reference_year: int | None = None):
    studies = b["prevalence"]
    if not studies:
        return (None, [])
    latest = sorted(studies, key=lambda s: int(s["fieldwork_year"]))[-1]
    return ((reference_year or 0) - int(latest["fieldwork_year"]), [latest.get("provenance")])


DERIVED: dict[str, Callable[..., tuple[Any, list]]] = {
    "market_live": d_market_live,
    "self_exclusion_program_type": d_self_exclusion_program_type,
    "deposit_limits_entered": d_deposit_limits_entered,
    "deposit_mandatory_default": d_deposit_mandatory_default,
    "deposit_required_at_signup": d_deposit_required_at_signup,
    "deposit_player_set_available": d_deposit_player_set_available,
    "advertising_rule_count": d_advertising_rule_count,
    "advertising_substantive_count": d_advertising_substantive_count,
    "legal_age_min": d_legal_age_min,
    "credit_card_allowed": d_credit_card_allowed,
    "pg_funding_mechanism": d_pg_funding_mechanism,
    "prevalence_searched": d_prevalence_searched,
    "prevalence_years_since_latest": d_prevalence_years_since_latest,
}

# Plain-language definitions shown on the report card page beside each input name.
DERIVED_DOC = {
    "market_live": "True when any legal_status row has market_segment regulated_sportsbook and status live.",
    "self_exclusion_program_type": "consumer_protections.self_exclusion.program_type; null when the section is absent.",
    "deposit_limits_entered": "True when consumer_protections.deposit_limits is present.",
    "deposit_mandatory_default": "consumer_protections.deposit_limits.mandatory_default.",
    "deposit_required_at_signup": "consumer_protections.deposit_limits.player_set_required_at_signup.",
    "deposit_player_set_available": "consumer_protections.deposit_limits.player_set_available.",
    "advertising_rule_count": "Number of rows in consumer_protections.advertising; null when the list is absent.",
    "advertising_substantive_count": "Rows in consumer_protections.advertising whose rule_type is not responsible_gambling_message_required.",
    "legal_age_min": "Minimum age across the legal_age rows; null when none are entered.",
    "credit_card_allowed": "consumer_protections.credit_card_deposits.allowed.",
    "pg_funding_mechanism": "funding_mechanism of the pg_funding.yaml record with the latest fiscal_year; null when the file is absent.",
    "prevalence_searched": "True when the profile is full or a prevalence study is on file; null for status-only profiles, which have not been searched for studies.",
    "prevalence_years_since_latest": "Rubric effective year minus the latest fieldwork_year among the state's prevalence studies; null when none.",
}


# ---------------------------------------------------------------- rule evaluation
def evaluate_when(when: Any, values: dict[str, Any]) -> bool:
    if when == "otherwise":
        return True
    if "any" in when:
        return any(evaluate_when(w, values) for w in when["any"])
    if "all" in when:
        return all(evaluate_when(w, values) for w in when["all"])
    if "not" in when:
        return not evaluate_when(when["not"], values)
    var, op = when["var"], when["op"]
    if var not in values:
        raise KeyError(f"rubric references unknown input {var!r}")
    v = values[var]
    target = when.get("value")
    if op == "is_null":
        return v is None
    if op == "not_null":
        return v is not None
    if v is None:
        return False  # comparisons against an absent value never match
    if op == "eq":
        return v == target
    if op == "ne":
        return v != target
    if op == "in":
        return v in target
    if op == "not_in":
        return v not in target
    if op in ("gte", "lte", "gt", "lt"):
        return {"gte": v >= target, "lte": v <= target, "gt": v > target, "lt": v < target}[op]
    raise ValueError(f"unknown operator {op!r}")


def when_vars(when: Any) -> set[str]:
    if when == "otherwise":
        return set()
    for k in ("any", "all"):
        if k in when:
            return set().union(*(when_vars(w) for w in when[k]))
    if "not" in when:
        return when_vars(when["not"])
    return {when["var"]}


# ---------------------------------------------------------------- grading
def grade_state(bundle: dict, rubric: dict) -> dict:
    profile = bundle["profile"]
    ref_year = int(str(rubric["effective_from"])[:4])
    values: dict[str, Any] = {}
    evidence: dict[str, list] = {}
    for name, fn in DERIVED.items():
        val, provs = fn(bundle, ref_year) if name == "prevalence_years_since_latest" else fn(bundle)
        values[name] = val
        evidence[name] = [p for p in provs if p]
    market = bool(values["market_live"])
    applicable = [c for c in rubric["criteria"] if market or c["applies_to"] == "all_states"]
    cards = []
    points = available = 0
    missing = []
    pending = 0
    for c in applicable:
        needed = {c["presence"]} | set().union(*(when_vars(s["when"]) for s in c["scoring"]))
        inputs = {n: values[n] for n in sorted(needed)}
        provs = []
        seen = set()
        for n in sorted(needed):
            for p in evidence.get(n, []):
                key = json.dumps(prov_summary(p), sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    provs.append(prov_summary(p))
        entry = {"criterion_id": c["criterion_id"], "max_points": c["max_points"], "inputs": inputs, "evidence": provs}
        if values[c["presence"]] is None:
            entry.update({"status": "not_entered", "points": None, "label": None, "condition": None})
            missing.append(c["criterion_id"])
        else:
            for s in c["scoring"]:
                if evaluate_when(s["when"], values):
                    entry.update({"status": "scored", "points": s["points"], "label": s.get("label"), "condition": s["condition"]})
                    break
            else:
                raise RuntimeError(f"{profile['abbr']}: no scoring row matched for {c['criterion_id']}")
            points += entry["points"]
            pending += sum(1 for p in provs if p and p.get("status") != "verified")
        available += c["max_points"]
        cards.append(entry)
    complete = not missing
    pct = round(points / available * 100, 1) if available and complete else None
    letter = None
    if complete and pct is not None:
        for band in sorted(rubric["grade_bands"], key=lambda b: -b["min_pct"]):
            if pct >= band["min_pct"]:
                letter = band["grade"]
                break
    entered = [c for c in cards if c["status"] == "scored"]
    return {
        "fips": str(profile["fips"]).zfill(2), "abbr": profile["abbr"], "name": profile["name"],
        "market": "regulated_market" if market else "no_regulated_market",
        "profile_completeness": profile.get("profile_completeness"),
        "criteria": cards,
        "points": points, "available": available,
        "points_entered": sum(c["max_points"] for c in entered),
        "pct": pct, "grade": letter,
        "status": "complete" if complete else "incomplete",
        "review": ("verified" if pending == 0 else "provisional") if complete else None,
        "inputs_pending_review": pending,
        "missing_criteria": missing,
    }


def fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(ROOT)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def compute(rubric_path: Path) -> dict:
    rubric = load_yaml(rubric_path)
    for c in rubric["criteria"]:
        for n in {c["presence"]} | set().union(*(when_vars(s["when"]) for s in c["scoring"])):
            if n not in DERIVED:
                raise SystemExit(f"rubric {rubric['version']}: criterion {c['criterion_id']} references unknown input {n!r}")
    prevalence_path = DATA / "outcomes" / "prevalence_studies.yaml"
    prevalence = load_yaml(prevalence_path) if prevalence_path.exists() else {"studies": []}
    state_dirs = sorted(d for d in (DATA / "states").iterdir() if (d / "profile.yaml").exists())
    states = [grade_state(load_bundle(d, prevalence), rubric) for d in state_dirs]
    states.sort(key=lambda s: s["abbr"])
    inputs = [rubric_path] + [p for d in state_dirs for p in (d / "profile.yaml", d / "pg_funding.yaml") if p.exists()]
    if prevalence_path.exists():
        inputs.append(prevalence_path)
    return {
        "rubric_version": rubric["version"], "rubric_status": rubric["status"], "effective_from": str(rubric["effective_from"]),
        "data_fingerprint": fingerprint(inputs),
        "derived_inputs": DERIVED_DOC,
        "summary": {
            "states": len(states),
            "graded": sum(1 for s in states if s["grade"]),
            "incomplete": sum(1 for s in states if s["status"] == "incomplete"),
            "no_regulated_market": sum(1 for s in states if s["market"] == "no_regulated_market"),
            "grades": {g: sum(1 for s in states if s["grade"] == g) for g in sorted({s["grade"] for s in states if s["grade"]})},
        },
        "states": states,
    }


def render(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", default=None, help="rubric file; default is the highest version under data/report_cards/rubric")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--state", default=None)
    a = ap.parse_args()
    rubric_path = Path(a.rubric) if a.rubric else sorted((DATA / "report_cards" / "rubric").glob("*.yaml"))[-1]
    doc = compute(rubric_path)
    out = OUT_DIR / f"{doc['rubric_version']}.json"
    if a.state:
        s = next(x for x in doc["states"] if x["abbr"] == a.state.upper())
        print(render(s))
        return 0
    text = render(doc)
    if a.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        print(f"wrote {out.relative_to(ROOT)}: {doc['summary']}")
        return 0
    if a.check:
        if not out.exists():
            print(f"grade check: {out.relative_to(ROOT)} is missing; run scripts/grade.py --write")
            return 1
        if out.read_text() != text:
            print(f"grade check: {out.relative_to(ROOT)} differs from a fresh computation; run scripts/grade.py --write and commit the result")
            return 1
        print(f"grade check: {out.relative_to(ROOT)} matches ({doc['summary']['graded']} graded, {doc['summary']['incomplete']} incomplete)")
        return 0
    print(render(doc["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
