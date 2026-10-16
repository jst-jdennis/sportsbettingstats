# Review log: state profile cross-check pass, 2026-10-16

Scope: the 48 jurisdictions that had status-only profiles after the Phase 1
draft (every state except Oklahoma, New Jersey and Kansas). Six research
agents, eight states each, worked from the brief in the pull request. They
could use web search only; no agent could open a regulator or legislature
page directly from the build container, and the shared search budget ran
out before every agent finished its list. Every record therefore remains
`pending_review`. Nothing in this pass is verified, and this log exists so
that the human reviewer knows where to look first.

## What changed

| Metric | Before | After |
| --- | --- | --- |
| Full profiles | 3 | 27 |
| Prediction market files | 3 | 13 |
| Provenance records | 247 | 431 |
| Records marked verified | 0 | 0 |

Full profiles after this pass: AZ, AR, CO, CT, DC, IN, IA, KY, LA, ME, MD,
MA, MI, MO (partial fields, see below), OH, OR, PA, TN, VT, VA, WV, WY
plus the original OK, NJ, KS. Status-only: AL, AK, CA, DE, FL, GA, HI, ID,
IL, MN, MS, MT, NE, NV, NH, NM, NY, NC, ND, RI, SC, SD, TX, UT, WA, WI.

## Corrections to seeded values

Each is recorded in the record's provenance notes as "Corrected from ...".

| State | Field | Old | New | Basis |
| --- | --- | --- | --- | --- |
| IN | retail and online authorized_on | 2019-05-08 | 2019-07-01 | HEA 1015 effective date, IGC Resolution 2020-82 |
| FL | regulator roles | licensing, enforcement, revenue_reporting | compact_compliance, enforcement | FGCC annual report |
| ID | authority citation | no statute | Idaho Const. art. III sec. 20 | legislature.idaho.gov |
| VT | online operator_model | commercial | lottery_monopoly | Act 63 summary |
| WI | online channel | not_authorized | authorized_not_launched, on_premises_only | Governor release, Oneida compact amendment |
| WY | retail authority and operator_model | statute, commercial | none, tribal_exclusive | HB 133 authorizes online only |
| WA | regulator roles | revenue_reporting | compact_compliance | WSGC |
| MT | authority citation | MCA 23-5-1001 | MCA Title 23 ch. 7 | leg.mt.gov |
| NE | authority type | ballot_measure | statute (LB 561) | statute history, Legislature report |
| NV | online authority type | statute | regulation (Reg 22) | NGCB |
| ME | retail status and operator_model | authorized_not_launched, tribal_exclusive | live, mixed | maine.gov/dps release; 8 M.R.S. 1206 |
| MD | authority type | ballot_measure | statute (Ch. 356 of 2021) | mgaleg |
| MS | on-premises mobile authority type | statute | regulation | MGC |
| OR | retail authority, operator models, Lottery roles | statute, mixed, licensing | compact, tribal_exclusive retail, lottery_monopoly online, operation | Lottery presentation on olis.oregonlegislature.gov |
| OH | regulator URL, authority effective date | homepage, none | sportsgaming page, 2022-03-23 | casinocontrol.ohio.gov |
| TN | regulator URL | tn.gov/swc.html | tn.gov/swac.html | tn.gov |

## Items the reviewer should check first

These are claims the agents could not confirm and flagged, ordered by how
much a wrong value would matter.

1. **Mississippi 2026 bills HB 1527 and HB 4074** (statewide online): enacted or not. If enacted, the online row changes.
2. **North Dakota compacts of 2022-12-02**: press says they allow on-reservation mobile wagering. If so, online becomes `tribal_lands_only`.
3. **North Carolina retail scope**: may be broader than tribal lands after S.L. 2023-42.
4. **Delaware online authorization**: seeded as 2009; likely 2012 HB 333.
5. **Louisiana 21.5 percent online rate**: effective date assumed 2025-08-01.
6. **Nevada tax tiers**: effective date assumed.
7. **Illinois tier thresholds**: 50 million and 100 million intermediate thresholds unconfirmed.
8. **New Hampshire legal age**: 18 per RSA 287-I:1; a 2025 bill to raise it is unconfirmed.
9. **Launch dates generally**: most seeded launch dates could not be confirmed on a primary page and are retained with a note. Confirmed: MO 2025-12-01, VT 2024-01-11, CT online 2021-10-19, WA retail 2021-09-09, DE retail 2018-06-05, all MA dates.

## Prediction market records added

Files now exist for AZ, CT, IL, KY, MI, NV, OH, RI, TN, WA (plus the
original NJ, OK, KS). Those with a located primary document URL: AZ
(azag.gov), CT (portal.ct.gov, two documents), IL (IGB PDFs for Kalshi and
Polymarket), KY (ag.ky.gov), MI (michigan.gov/ag), NV (gaming.nv.gov), OH
(OCCC minutes PDF), WA (WSGC notice PDF). Those where the action is
recorded but the release itself was not located: RI, TN, and the Robinhood
and Crypto.com letters in IL. The reviewer may prefer to hold RI and TN
until the releases are archived.

Known actions not yet recorded because no primary URL was found: Maryland
cease and desist (2025-04-07) and KalshiEX v. Martin; Massachusetts AG v.
KalshiEX (Suffolk Superior Court); Missouri AG cease and desist; Montana
GCD letters (2025-03-26, 2026-04-06); Wisconsin DOJ suits (2026-04-23);
Utah (Kalshi v. Utah, D. Utah); Washington AG lawsuit and King County orders
are recorded with press dates and flagged.

## Publishers added to the registry after this pass

de-governor, ny-governor, nh-secretary-of-state, dc-otr,
fl-seminole-tribal-gaming-commission, wi-attorney-general-doj,
ar-secretary-of-state, co-legislative-council, mt-doj-gambling-control,
ca-secretary-of-state.

## Method notes for the next pass

- Run from a networked machine so agents can open and archive the primary
  page. Search snippets were enough to correct obvious errors but not to
  verify dates.
- Budget about 10 searches per live state; six agents sharing one budget
  of 200 per turn exhausted it with roughly a third of planned checks left.
- The two-person rule still applies: only a human reviewer flips a record
  to verified, and only after opening the cited document.
