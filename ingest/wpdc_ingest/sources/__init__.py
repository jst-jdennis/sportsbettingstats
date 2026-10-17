"""One module per source. Register new sources in REGISTRY."""
from __future__ import annotations

from importlib import import_module

REGISTRY = {
    "uscourts-bankruptcy-f2": "wpdc_ingest.sources.uscourts_bankruptcy:USCourtsBankruptcyF2",
    "nj-dge-sports-wagering-monthly": "wpdc_ingest.sources.nj_dge_sports_wagering:NJDGESportsWagering",
    "census-pep-state-totals": "wpdc_ingest.sources.census_population:CensusPopulation",
    "pa-pgcb-sports-wagering-monthly": "wpdc_ingest.sources.pa_pgcb_sports_wagering:PAPGCBSportsWagering",
    "ks-lottery-sports-wagering": "wpdc_ingest.sources.ks_lottery_sports_wagering:KSLotterySportsWagering",
    "oh-occc-sports-gaming-monthly": "wpdc_ingest.sources.oh_occc_sports_gaming:OHOCCCSportsGaming",
    "ny-gaming-commission-mobile-sports-monthly": "wpdc_ingest.sources.ny_gaming_commission_mobile_sports:NYGamingCommissionMobileSports",
}


def load(source_id: str):
    mod, cls = REGISTRY[source_id].split(":")
    return getattr(import_module(mod), cls)()
