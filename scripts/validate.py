#!/usr/bin/env python3
"""Validate every data file against its schema and the cross-file rules.

Run from the repository root. Exits non-zero on any error. This is the same
check the site build and CI run, and the same one the ingestion CLI runs
before it opens a pull request.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from frictionless import Resource as FrResource, validate as fr_validate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCHEMAS = ROOT / "schemas"

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def load_registry() -> Registry:
    resources = []
    for p in SCHEMAS.glob("*.schema.json"):
        doc = json.loads(p.read_text())
        resources.append((doc["$id"], Resource.from_contents(doc)))
        # Also register by bare filename so relative $refs resolve.
        resources.append((p.name, Resource.from_contents(doc)))
    return Registry().with_resources(resources)


REGISTRY = load_registry()


def validator_for(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text())
    return Draft202012Validator(schema, registry=REGISTRY, format_checker=FormatChecker())


def validate_yaml(path: Path, schema_name: str) -> dict | None:
    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        err(f"{path}: YAML parse error: {e}")
        return None
    v = validator_for(schema_name)
    for e in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(x) for x in e.path) or "<root>"
        err(f"{path}: {loc}: {e.message}")
    return doc


def validate_csv(path: Path, schema_name: str) -> list[dict]:
    schema_path = SCHEMAS / f"{schema_name}.tableschema.json"
    res = FrResource(path=str(path.relative_to(ROOT)), basepath=str(ROOT), schema=str(schema_path.relative_to(ROOT)))
    report = fr_validate(res)
    if not report.valid:
        for task in report.tasks:
            for e in task.errors:
                err(f"{path}: {e.message}")
    try:
        return res.read_rows()
    except Exception as e:  # noqa: BLE001
        err(f"{path}: could not read rows: {e}")
        return []


# ---------- Collect provenance blocks recursively ----------

def walk_provenance(obj, path: str, out: list[tuple[str, dict]]):
    if isinstance(obj, dict):
        if "provenance" in obj and isinstance(obj["provenance"], dict):
            out.append((path, obj["provenance"]))
        for k, v in obj.items():
            walk_provenance(v, f"{path}/{k}", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_provenance(v, f"{path}[{i}]", out)


def main() -> int:
    # Sources registry
    sources_doc = validate_yaml(DATA / "sources" / "sources.yaml", "sources") or {"sources": []}
    sources = {s["source_id"]: s for s in sources_doc.get("sources", [])}
    if len(sources) != len(sources_doc.get("sources", [])):
        err("sources.yaml: duplicate source_id")

    # Reference tables
    states = validate_csv(DATA / "reference" / "states.csv", "states")
    fips_set = {r["fips"] for r in states}
    population = validate_csv(DATA / "reference" / "population.csv", "population")
    districts = validate_csv(DATA / "reference" / "districts.csv", "districts")
    for r in districts:
        if r["fips"] not in fips_set:
            err(f"districts.csv: unknown fips {r['fips']} for {r['district_code']}")

    prov_blocks: list[tuple[str, dict]] = []
    csv_prov_rows: list[tuple[str, dict]] = []
    for r in population:
        csv_prov_rows.append(("population.csv", r))

    # State directories
    seen_profile_fips = set()
    for st_dir in sorted((DATA / "states").iterdir()):
        if not st_dir.is_dir():
            continue
        prof_path = st_dir / "profile.yaml"
        if not prof_path.exists():
            err(f"{st_dir}: missing profile.yaml")
            continue
        prof = validate_yaml(prof_path, "state_profile")
        if prof:
            if prof["fips"] not in fips_set:
                err(f"{prof_path}: fips {prof['fips']} not in states.csv")
            if st_dir.name != prof["abbr"].lower():
                err(f"{prof_path}: directory {st_dir.name} does not match abbr {prof['abbr']}")
            seen_profile_fips.add(prof["fips"])
            walk_provenance(prof, str(prof_path.relative_to(ROOT)), prov_blocks)
            # No two live rows for the same channel with overlapping open periods
            by_channel = defaultdict(list)
            for row in prof["legal_status"]:
                by_channel[row["channel"]].append(row)
            for ch, rows in by_channel.items():
                live = [r for r in rows if r["status"] == "live"]
                if len(live) > 1 and len({r["scope"] for r in live}) != len(live):
                    err(f"{prof_path}: more than one live {ch} row with the same scope")
            if prof.get("profile_completeness") == "full":
                for key in ("legal_age", "tax", "consumer_protections", "summary"):
                    if not prof.get(key):
                        err(f"{prof_path}: profile_completeness is full but {key} is missing")
        for name, schema in (("pg_funding.yaml", "pg_funding"), ("prediction_markets.yaml", "prediction_markets")):
            p = st_dir / name
            if p.exists():
                doc = validate_yaml(p, schema)
                if doc:
                    if doc.get("fips") != (prof or {}).get("fips"):
                        err(f"{p}: fips does not match profile")
                    walk_provenance(doc, str(p.relative_to(ROOT)), prov_blocks)
    missing = fips_set - seen_profile_fips
    if missing:
        warn(f"states without a profile directory: {sorted(missing)}")

    # Outcomes
    for name, schema in (("handle_revenue.csv", "handle_revenue"), ("bankruptcy.csv", "bankruptcy"), ("helpline.csv", "helpline")):
        p = DATA / "outcomes" / name
        if p.exists():
            rows = validate_csv(p, schema)
            keyed = defaultdict(list)
            for r in rows:
                csv_prov_rows.append((name, r))
                if r["fips"] not in fips_set:
                    err(f"{name}: unknown fips {r['fips']}")
                k = tuple(r[c] for c in ("fips",) + (("channel", "market_segment") if "channel" in r else ("measure", "chapter") if "measure" in r else ("contact_type",)))
                if r["status"] != "superseded":
                    keyed[k].append((r["period_start"], r["period_end"]))
            for k, periods in keyed.items():
                periods.sort()
                for (s1, e1), (s2, e2) in zip(periods, periods[1:]):
                    if s2 <= e1:
                        err(f"{name}: overlapping periods for {k}: {s1}..{e1} and {s2}..{e2}")

    # Research, legislation, rubric
    for p in sorted((DATA / "research" / "papers").glob("*.yaml")):
        doc = validate_yaml(p, "paper")
        if doc:
            if doc["slug"] != p.stem:
                err(f"{p}: slug {doc['slug']} does not match filename")
            labels = {v["version_label"] for v in doc["versions"]}
            ids = {f["figure_id"] for f in doc["key_figures"]}
            for f in doc["key_figures"]:
                if f["version_label"] not in labels:
                    err(f"{p}: key figure {f['figure_id']} cites unknown version {f['version_label']}")
                if f["status"] == "superseded" and f.get("superseded_by") not in ids:
                    err(f"{p}: superseded figure {f['figure_id']} must name superseded_by")
            walk_provenance(doc, str(p.relative_to(ROOT)), prov_blocks)
    for p in sorted((DATA / "legislation" / "bills").glob("*.yaml")):
        doc = validate_yaml(p, "bill")
        if doc:
            if doc["slug"] != p.stem:
                err(f"{p}: slug does not match filename")
            if doc["fips"] not in fips_set:
                err(f"{p}: unknown fips")
            walk_provenance(doc, str(p.relative_to(ROOT)), prov_blocks)
    for p in sorted((DATA / "report_cards" / "rubric").glob("*.yaml")):
        doc = validate_yaml(p, "rubric")
        if doc:
            for c in doc["criteria"]:
                if max(s["points"] for s in c["scoring"]) != c["max_points"]:
                    err(f"{p}: criterion {c['criterion_id']} max_points does not equal its highest scoring points")

    # Cross-file provenance rules
    today = date.today()
    for where, pv in prov_blocks:
        sid = pv.get("source_id")
        if sid not in sources:
            err(f"{where}: source_id {sid!r} not in sources.yaml")
            continue
        if sources[sid]["tier"] == "tertiary":
            err(f"{where}: tertiary source {sid} may not be cited for a fact or figure")
        try:
            if date.fromisoformat(str(pv["retrieved_at"])) > today:
                err(f"{where}: retrieved_at is in the future")
        except ValueError:
            pass
    for where, r in csv_prov_rows:
        sid = r.get("source_id")
        if sid not in sources:
            err(f"{where}: source_id {sid!r} not in sources.yaml")
        elif sources[sid]["tier"] == "tertiary":
            err(f"{where}: tertiary source {sid} may not be cited for a figure")
        if r.get("status") == "verified" and not r.get("reviewed_by"):
            err(f"{where}: verified row without reviewed_by")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"validate: {len(errors)} error(s), {len(warnings)} warning(s), {len(prov_blocks) + len(csv_prov_rows)} provenance records checked")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
