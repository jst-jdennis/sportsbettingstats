"""One module per source. Register new sources in REGISTRY."""
from __future__ import annotations

from importlib import import_module

REGISTRY = {
    "uscourts-bankruptcy-f2": "wpdc_ingest.sources.uscourts_bankruptcy:USCourtsBankruptcyF2",
    "nj-dge-sports-wagering-monthly": "wpdc_ingest.sources.nj_dge_sports_wagering:NJDGESportsWagering",
    "census-pep-state-totals": "wpdc_ingest.sources.census_population:CensusPopulation",
}


def load(source_id: str):
    mod, cls = REGISTRY[source_id].split(":")
    return getattr(import_module(mod), cls)()
