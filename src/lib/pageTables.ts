// The registry of every table and chart on the site, one function per page.
// Pages render these objects through DataTable.astro and Chart.astro; the
// catch-all CSV endpoint serves the same objects as files; the fact sheets
// read the same rows. Add a table here and it appears in the page's
// downloads box and gets a CSV without any further wiring.
import fs from 'node:fs';
import type { Provenance, StateProfile, Bill, Paper, StateGrade, GradeEvidence } from './data';
import {
  profiles, pgFunding, predictionMarkets, bills, papers, population, prevalenceStudies, sources, rubrics, grades,
  headlineStatus, HEADLINE_LABEL, scopeQualifiers, earliestLaunch, fmtDate, pct, label, OUTCOME_LABEL, effectFigures, adoptionByYear,
  bankruptcy, handleRevenue, helpline, reviewSummary, source,
} from './data';
import { revenueChart, bankruptcyChart, bankruptcyTable, revenueTable, helplineChart, helplineTable, hlFor, hrFor, bkFor, per100k, MIN_POINTS, type SeriesChart } from './seriesCharts';
import { D, USD, N, R, L, seriesProv, type DataTable, type PageTables, type Cell } from './tables';

const BASE = (import.meta.env.BASE_URL ?? '/').replace(/\/$/, '');
export const statePath = (p: { abbr: string }) => `/states/${p.abbr.toLowerCase()}/`;
const stateHref = (p: { abbr: string }) => BASE + statePath(p);
const billHref = (b: Bill) => `${BASE}/legislation/${b.slug}/`;
const paperHref = (p: Paper) => `${BASE}/research/${p.slug}/`;
const yesNo = (v: unknown) => v == null ? '' : v ? 'yes' : 'no';
const short = (p: Paper) => `${p.authors[0].split(' ').pop()}${p.authors.length > 1 ? ' et al.' : ''} (${p.year_first_circulated})`;
const PREV_MEASURE: Record<string, string> = { past_year_gambling: 'Gambled in past year', past_30_day_gambling: 'Gambled in past 30 days', past_year_sports_betting: 'Bet on sports in past year', at_risk_or_problem: 'At risk or problem gambling', low_risk: 'Low risk', moderate_risk: 'Moderate risk', high_risk: 'High risk or probable disorder' };

// ---------- Home and state index ----------

export function homePage(): PageTables {
  const ps = profiles();
  const page = '/';
  return { page, title: 'Legal status of sports wagering by state', tables: [{
    id: 'status', page, csv: '/states/status.csv', title: 'Headline legal status of regulated sports wagering, every state and DC',
    head: ['State', 'Status', 'Qualifiers', 'First launch', 'Profile', 'Review'],
    rows: ps.map((p) => { const hs = headlineStatus(p); return [L(p.name, stateHref(p)), HEADLINE_LABEL[hs], scopeQualifiers(p).join('; '), hs === 'none' ? '' : D(earliestLaunch(p)), p.profile_completeness === 'full' ? 'Full' : 'Status only', p.legal_status.some((r) => r.provenance.status !== 'verified') ? 'pending' : 'verified']; }),
    note: 'Regulated sportsbooks only; prediction markets are tracked separately. Pending means at least one legal status row is entered with a source and awaiting a second reviewer.',
  }] };
}

/** States with a live channel and their first wager by channel, ordered by first wager. */
export function launches() {
  const firstOf = (p: StateProfile, ch: 'retail' | 'online') => p.legal_status.filter((r) => r.channel === ch && r.launched_on).map((r) => r.launched_on!).sort()[0] ?? null;
  return profiles().map((p) => ({ p, retail: firstOf(p, 'retail'), online: firstOf(p, 'online') })).filter((x) => x.retail || x.online)
    .sort((a, b) => ([a.retail, a.online].filter(Boolean).sort()[0]!).localeCompare([b.retail, b.online].filter(Boolean).sort()[0]!));
}

export function statesIndexPage(): PageTables {
  const page = '/states/';
  return { page, title: 'State profiles', tables: [{
    id: 'launches', page, title: 'First legal wager in each state, by channel',
    head: ['State', 'First retail wager', 'First online wager', 'Qualifiers'],
    rows: launches().map(({ p, retail, online }) => [L(p.name, stateHref(p)), D(retail), D(online), scopeQualifiers(p).join('; ')]),
    note: 'States without a live channel are not listed. Mobile wagering that works only on licensed premises counts as online, per the classification rule on the methodology page.',
  }] };
}

// ---------- State page ----------

export type StateEvent = { date: string; cls: string; title: string; label?: string; row: string; href?: string };
/** Every dated event in a state's files: authorizations, first wagers, bill actions and votes, enforcement actions, rulings. */
export function stateEvents(p: StateProfile): StateEvent[] {
  const pm = predictionMarkets(p.abbr);
  const events: StateEvent[] = [];
  for (const r of p.legal_status) {
    const ch = label(r.channel);
    if (r.authorized_on) events.push({ row: `${ch} wagering`, date: r.authorized_on, cls: 's0', title: `${ch} authorized ${fmtDate(r.authorized_on)}${r.authority ? `: ${r.authority.citation}` : ''}`, label: 'authorized' });
    if (r.launched_on) events.push({ row: `${ch} wagering`, date: r.launched_on, cls: r.channel === 'online' ? 's2' : 's1', title: `First ${ch} wager ${fmtDate(r.launched_on)}${r.scope !== 'statewide' && r.scope !== 'not_applicable' ? ` (${label(r.scope)})` : ''}`, label: 'first wager' });
  }
  for (const b of bills().filter((b) => b.fips === p.fips)) {
    for (const a of b.actions ?? []) events.push({ row: b.bill_number, date: a.date, cls: 's0', title: `${b.bill_number}, ${fmtDate(a.date)}, ${label(a.chamber)}: ${a.action_text}`, href: billHref(b) });
    for (const v of b.votes ?? []) events.push({ row: b.bill_number, date: v.date, cls: 's3', title: `${b.bill_number}, ${fmtDate(v.date)}, ${label(v.chamber)} vote: ${v.yeas} to ${v.nays}, ${v.result}`, label: `${v.result} ${v.yeas} to ${v.nays}`, href: billHref(b) });
  }
  for (const a of pm?.state_actions ?? []) if (a.date) events.push({ row: 'Prediction markets', date: a.date, cls: 's3', title: `${fmtDate(a.date)}: ${label(a.action_type)} by ${a.issuing_body} against ${a.target}`, label: label(a.action_type) });
  for (const c of pm?.litigation ?? []) for (const r of c.rulings ?? []) if (r.date) events.push({ row: 'Prediction markets', date: r.date, cls: 's3', title: `${fmtDate(r.date)}, ${r.court}: ${r.summary}`, label: 'ruling' });
  return events;
}

const taxRate = (t: any): string => {
  const parts: string[] = [];
  if (t.rate != null) parts.push(pct(t.rate));
  else if (t.tiers) parts.push(t.tiers.map((x: any) => `${pct(x.rate)} ${x.threshold_to != null ? `from $${Number(x.threshold_from).toLocaleString()} to $${Number(x.threshold_to).toLocaleString()}` : `above $${Number(x.threshold_from).toLocaleString()}`}`).join('; '));
  else parts.push('none');
  if (t.per_wager_fee_cents != null) parts.push(`${t.per_wager_fee_cents} cents per wager`);
  return parts.join('; ');
};

/** Rates from every prevalence study for the given states, one row per published rate. */
function prevalenceTable(page: string, fipsList: string[] | null, withState: boolean): DataTable {
  const names = new Map(profiles().map((p) => [p.fips, p.name]));
  const studies = prevalenceStudies().filter((s) => !fipsList || fipsList.includes(s.fips));
  const rows: Cell[][] = [], prov: Provenance[] = [];
  for (const s of studies) for (const r of s.rates) {
    rows.push([...(withState ? [names.get(s.fips) ?? s.fips] : []), L(s.title, s.report_url), s.fieldwork_year, PREV_MEASURE[r.measure] ?? label(r.measure), r.definition, R(r.value_pct, 1), R(r.ci_low_pct ?? null, 1), R(r.ci_high_pct ?? null, 1), r.denominator ?? '', s.instrument, N(s.sample_size)]);
    prov.push(r.provenance);
  }
  return {
    id: 'prevalence', page, title: 'Prevalence study rates as published', prov, rows,
    head: [...(withState ? ['State'] : []), 'Study', 'Fieldwork year', 'Measure', 'Definition', 'Rate (%)', 'CI low (%)', 'CI high (%)', 'Denominator', 'Instrument', 'Sample size'],
    note: 'Rates are copied as published and never recomputed. Instruments, thresholds, denominators and survey modes differ between studies; the comparability note on each study record says which pairs may be compared.',
  };
}

const stateCache = new Map<string, PageTables>();
export function statePage(p: StateProfile): PageTables {
  const hit = stateCache.get(p.abbr); if (hit) return hit;
  const page = statePath(p);
  const at = (id: string) => ({ page, id });
  const pg = pgFunding(p.abbr);
  const pop = population().filter((r) => r.fips === p.fips && r.status !== 'superseded').sort((a, b) => Number(b.year) - Number(a.year))[0];
  const perResident = (amount: number | null | undefined): Cell => amount == null || !pop ? 'not computed' : { text: `$${(amount / Number(pop.population)).toFixed(2)}`, value: Math.round((amount / Number(pop.population)) * 100) / 100 };
  const events = stateEvents(p).sort((a, b) => a.date.localeCompare(b.date));
  const tables: DataTable[] = [];
  if (events.length) tables.push({ ...at('events'), title: `${p.name}: dated events in this profile`, head: ['Subject', 'Date', 'Event'], rows: events.map((e) => [e.row, D(e.date), L(e.title, e.href)]), note: 'Authorization dates, first wagers, bill actions and votes, prediction market enforcement actions and rulings, as entered in the state files.' });
  tables.push({
    ...at('legal-status'), title: `${p.name}: legal status of regulated sports wagering by channel`,
    head: ['Channel', 'Status', 'Scope', 'Authorized', 'First wager', 'Authority', 'Operator model', 'Notes'],
    rows: p.legal_status.map((r) => [label(r.channel), label(r.status), r.scope === 'not_applicable' ? '' : label(r.scope), r.status === 'not_authorized' ? '' : D(r.authorized_on), r.status === 'not_authorized' ? '' : D(r.launched_on), r.authority ? L(r.authority.citation, r.authority.url) : '', label(r.operator_model), r.notes ?? '']),
    prov: p.legal_status.map((r) => r.provenance),
  });
  tables.push({
    ...at('regulators'), title: `${p.name}: regulators`, head: ['Regulator', 'Type', 'Roles'],
    rows: p.regulators.map((r) => [L(r.name, r.url), label(r.type), r.roles.map(label).join(', ')]), prov: p.regulators.map((r) => r.provenance),
  });
  if (p.legal_age?.length) tables.push({ ...at('legal-age'), title: `${p.name}: minimum age to wager`, head: ['Age', 'Scope', 'Authority'], rows: p.legal_age.map((a) => [a.age, label(a.scope), a.authority_citation ?? '']), prov: p.legal_age.map((a) => a.provenance) });
  if (p.tax?.length) tables.push({
    ...at('tax'), title: `${p.name}: sports wagering tax structure`,
    head: ['Channel', 'Basis', 'Rate', 'Effective from', 'Effective to', 'Promotional deductions', 'Destination', 'Authority'],
    rows: p.tax.map((t: any) => [label(t.channel), label(t.basis), taxRate(t), D(t.effective_from), t.effective_to ? D(t.effective_to) : 'onward', t.promo_deduction_rule ?? '', t.destination ? t.destination.map((d: any) => d.share != null ? `${d.fund_name} (${pct(d.share)})` : d.fund_name).join('; ') : '', t.authority_citation ?? '']),
    prov: p.tax.map((t: any) => t.provenance),
    note: 'Headline rates are not comparable across states without the basis and the promotional deduction rule, both given per row.',
  });
  if (pg?.records?.length) tables.push({
    ...at('funding'), title: `${p.name}: problem gambling funding by fiscal year`,
    head: ['Fiscal year', 'Amount', 'Amount type', 'Per resident', 'Mechanism', 'Mechanism text', 'Authority', 'Administering agency', 'Covers'],
    rows: pg.records.map((r: any) => [`FY${r.fiscal_year}`, USD(r.amount_usd, 'not entered'), label(r.amount_type), perResident(r.amount_usd), label(r.funding_mechanism), r.mechanism_text ?? '', r.authority_citation ?? '', r.administering_agency ?? '', r.includes ? r.includes.join(', ') : '']),
    prov: pg.records.map((r: any) => r.provenance), num: [1, 3],
    note: pop ? `Per resident divides the amount by the Census population estimate for ${pop.year} (Vintage ${pop.vintage}, ${label(pop.status)}); it is recomputed on every build and never stored.` : 'No population row on file, so nothing per resident is computed.',
  });
  const hr = hrFor(p.fips);
  if (hr.length) tables.push(revenueTable(p, at('revenue'), hr));
  const bk = bkFor(p.fips).filter((r) => r.chapter === 'all_nonbusiness');
  if (bk.length) tables.push(bankruptcyTable(p, at('bankruptcy'), bk));
  const hl = hlFor(p.fips);
  if (hl.length) tables.push(helplineTable(hl, at('helpline'), `${p.name}: problem gambling helpline contacts by period`));
  if (prevalenceStudies(p.fips).length) tables.push(prevalenceTable(page, [p.fips], false));
  // Charts share the registry's table objects, so the chart's data table and its CSV are the same rows the page
  // table shows. The quarterly bankruptcy chart plots a subset of the bankruptcy table, so it registers its own.
  const charts: SeriesChart[] = [];
  const rev = revenueChart(p, at('revenue')); if (rev) { rev.table = tables.find((t) => t.id === 'revenue')!; charts.push(rev); }
  const bq = bankruptcyChart(p, at('bankruptcy-quarterly')); if (bq) { tables.push(bq.table); charts.push(bq); }
  const hlc = helplineChart(p, at('helpline')); if (hlc) { hlc.table = tables.find((t) => t.id === 'helpline')!; charts.push(hlc); }
  chartCache.set(p.abbr, charts);
  const out = { page, title: `${p.name}: sports wagering and prediction markets`, tables, factsheet: true };
  stateCache.set(p.abbr, out);
  return out;
}
const chartCache = new Map<string, SeriesChart[]>();
/** The series charts on a state page (revenue, quarterly bankruptcy, helpline), each carrying its registered table. */
export function stateCharts(p: StateProfile): SeriesChart[] { statePage(p); return chartCache.get(p.abbr)!; }

// ---------- Outcomes ----------

let outcomesCache: PageTables | null = null;
export interface OutcomesCharts { bankruptcy: { p: StateProfile; c: SeriesChart }[]; helpline: { p: StateProfile; c: SeriesChart }[]; revenue: { p: StateProfile; c: SeriesChart }[] }
let outcomesChartCache: OutcomesCharts | null = null;
/** The per-state series charts shown on the outcomes page, computed once with the page's tables. */
export function outcomesCharts(): OutcomesCharts { outcomesPage(); return outcomesChartCache!; }
/** Latest twelve-month bankruptcy period on file and every state's rate for it, highest first. */
export function bankruptcyCrossSection() {
  const byFips = new Map(profiles().map((p) => [p.fips, p]));
  const bkAll = bankruptcy().filter((r) => r.measure === 'twelve_months_ending' && r.chapter === 'all_nonbusiness');
  const period = bkAll.map((r) => r.period_end).sort().pop() ?? null;
  const group = (hs: string): 'online' | 'retail' | 'none' => hs === 'retail_and_online' || hs === 'online_only' ? 'online' : hs === 'retail_only' ? 'retail' : 'none';
  const rows = bkAll.filter((r) => r.period_end === period).map((r) => { const p = byFips.get(r.fips)!; return { p, r, pk: per100k(Number(r.filings), r.fips, Number(r.period_end.slice(0, 4))), group: group(headlineStatus(p)) }; }).filter((x) => x.pk).sort((a, b) => b.pk!.value - a.pk!.value);
  return { period, rows };
}
export const BK_GROUP = { online: { cls: 's2', name: 'Online wagering live' }, retail: { cls: 's1', name: 'Retail wagering only' }, none: { cls: 's0', name: 'No live wagering' } } as const;
export function outcomesPage(): PageTables {
  if (outcomesCache) return outcomesCache;
  const page = '/outcomes/';
  const at = (id: string) => ({ page, id });
  const figs = effectFigures();
  const byFips = new Map(profiles().map((p) => [p.fips, p]));
  const tables: DataTable[] = [];
  tables.push({
    ...at('estimates'), title: 'Estimated effects of legalization from the research library',
    head: ['Outcome', 'Figure', 'As stated', 'Charted value', 'Unit', 'Range low', 'Range high', 'Paper', 'Unit of effect', 'Specification'],
    rows: figs.map(({ paper, fig }) => [OUTCOME_LABEL[fig.outcome_domain] ?? label(fig.outcome_domain), fig.description, fig.value_text, fig.value_numeric, label(fig.value_unit), fig.range_low ?? '', fig.range_high ?? '', L(short(paper), paperHref(paper), paper.title), label(paper.unit_of_effect), fig.specification ?? '']),
    prov: figs.map(({ fig }) => fig.provenance),
    note: 'Each figure is from a different paper, dataset and design; nothing is pooled. Positive values mean the outcome rose. A population average is over everyone in a state, bettors and non-bettors alike, and is not comparable with a household-level figure.',
  });
  const adoption = adoptionByYear();
  tables.push({ ...at('adoption'), title: 'States with live sports wagering at year end', head: ['Year end', 'Any channel live', 'Retail live', 'Online live'], rows: adoption.map((a) => [a.year, a.any, a.retail, a.online]), note: 'Count of states and the District of Columbia whose profile records a first legal wager on or before December 31 of each year.' });
  // Cross-state bankruptcy comparison for the latest twelve-month period on file.
  const { period: bkPeriod, rows: bkStates } = bankruptcyCrossSection();
  if (bkStates.length) tables.push({
    ...at('bankruptcy-by-state'), title: `Nonbusiness bankruptcy filings per 100,000 residents by state, twelve months ending ${fmtDate(bkPeriod)}`,
    head: ['State', 'Legal status at period end', 'Filings', 'Per 100,000', 'Population', 'Population year'],
    rows: bkStates.map(({ p, r, pk, group }) => [L(p.name, stateHref(p)), BK_GROUP[group].name, N(r.filings), R(pk!.value, 1), N(pk!.pop!.population), pk!.pop!.year]),
    prov: bkStates.map(({ r }) => seriesProv(r)),
    note: 'A cross-section, not an effect estimate. States differ in bankruptcy exemptions, income, debt levels, medical costs and court practice, all of which move filing rates more than any single policy.',
  });
  const all = profiles();
  const charts: OutcomesCharts = { bankruptcy: [], helpline: [], revenue: [] };
  for (const p of all) { const c = bankruptcyChart(p, at(`bankruptcy-${p.abbr.toLowerCase()}`)); if (c) { charts.bankruptcy.push({ p, c }); if (p.profile_completeness === 'full') tables.push(c.table); } }
  for (const p of all) { const c = helplineChart(p, at(`helpline-${p.abbr.toLowerCase()}`)); if (c) { charts.helpline.push({ p, c }); tables.push(c.table); } }
  const hlRest = helpline().filter((r) => !charts.helpline.some((x) => x.p.fips === r.fips));
  if (hlRest.length) tables.push(helplineTable(hlRest, at('helpline'), 'Problem gambling helpline contacts, states with fewer than three periods on file', (f) => byFips.get(f)?.name ?? f));
  for (const p of all) { const c = revenueChart(p, at(`revenue-${p.abbr.toLowerCase()}`)); if (c) { charts.revenue.push({ p, c }); tables.push(c.table); } }
  outcomesChartCache = charts;
  if (prevalenceStudies().length) tables.push(prevalenceTable(page, null, true));
  for (const name of ['handle_revenue', 'bankruptcy', 'helpline']) {
    const s = JSON.parse(fs.readFileSync(`schemas/${name}.tableschema.json`, 'utf8'));
    tables.push({ ...at(`schema-${name.replace(/_/g, '-')}`), title: `Schema of data/outcomes/${name}.csv`, head: ['Field', 'Type', 'Constraints'], rows: s.fields.map((f: any) => [f.name, f.type, f.constraints ? Object.entries(f.constraints).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' | ') : v}`).join('; ') : '']), note: s.description ?? null });
  }
  outcomesCache = { page, title: 'Outcomes', tables };
  return outcomesCache;
}

// ---------- Legislation ----------

export function legislationIndexPage(): PageTables {
  const page = '/legislation/';
  const bs = bills();
  const names = new Map(profiles().map((p) => [p.fips, p.name]));
  return { page, title: 'Legislation tracker', tables: [
    { id: 'actions', page, title: 'Bill actions and votes over time', head: ['Bill', 'Date', 'Chamber', 'Event'],
      rows: bs.flatMap((b) => [...(b.actions ?? []).map((a: any) => [L(`${names.get(b.fips)} ${b.bill_number}`, billHref(b)), D(a.date), label(a.chamber), a.action_text]), ...(b.votes ?? []).map((v: any) => [L(`${names.get(b.fips)} ${b.bill_number}`, billHref(b)), D(v.date), label(v.chamber), `Vote: ${v.motion}, ${v.yeas} to ${v.nays}, ${v.result}`])]),
      note: 'Only actions entered with a source appear; each bill page carries the source for every action and vote.' },
    { id: 'bills', page, title: 'All bills in the tracker', head: ['State', 'Bill', 'Title', 'Session', 'Segment', 'Status', 'Status date'],
      rows: bs.map((b) => [names.get(b.fips) ?? b.fips, L(b.bill_number, billHref(b)), b.title, b.session, b.market_segment.map(label).join(', '), label(b.status), D(b.status_date)]), prov: bs.map((b) => b.provenance) },
  ] };
}

export function billPage(b: Bill): PageTables {
  const st = profiles().find((p) => p.fips === b.fips)!;
  const page = `/legislation/${b.slug}/`;
  const tables: DataTable[] = [];
  if (b.votes?.length) tables.push({ id: 'votes', page, title: `${st.name} ${b.bill_number}: recorded votes`, head: ['Date', 'Chamber', 'Motion', 'Yeas', 'Nays', 'Result'], rows: b.votes.map((v: any) => [D(v.date), label(v.chamber), v.motion, v.yeas ?? '', v.nays ?? '', v.result]), prov: b.votes.map((v: any) => v.provenance), num: [3, 4] });
  if (b.actions?.length) tables.push({ id: 'actions', page, title: `${st.name} ${b.bill_number}: recorded actions`, head: ['Date', 'Chamber', 'Action'], rows: b.actions.map((a: any) => [D(a.date), label(a.chamber), a.action_text]), prov: b.actions.map((a: any) => a.provenance) });
  return { page, title: `${st.name} ${b.bill_number} (${b.session})`, tables };
}

// ---------- Research ----------

export function researchIndexPage(): PageTables {
  const page = '/research/';
  const ps = papers();
  return { page, title: 'Research library', tables: [{
    id: 'versions', page, title: 'Papers in the library and the dates of each version', head: ['Paper', 'Authors', 'Version', 'Date', 'Status of this version', 'What changed'],
    rows: ps.flatMap((p) => p.versions.map((v: any, i: number) => [L(p.title, paperHref(p)), p.authors.join(', '), v.version_label, D(v.date), i === p.versions.length - 1 ? label(p.publication_status) : 'working paper', v.changes_summary])),
    note: 'Dates are as precise as the document states them; a version dated only to a month or year is placed at its start.',
  }] };
}

export function paperPage(p: Paper): PageTables {
  const page = `/research/${p.slug}/`;
  return { page, title: p.title, tables: [{
    id: 'key-figures', page, title: `${p.title}: key figures`,
    head: ['Figure', 'Value as stated', 'Numeric value', 'Unit', 'Range low', 'Range high', 'Specification', 'Page or table', 'Version', 'Status', 'Superseded by'],
    rows: p.key_figures.map((f: any) => [f.description, f.provenance.status === 'unverified' ? 'not entered' : f.value_text, f.value_numeric ?? '', label(f.value_unit), f.range_low ?? '', f.range_high ?? '', f.specification ?? '', f.page_or_table ?? '', f.version_label, label(f.status), f.superseded_by ?? '']),
    prov: p.key_figures.map((f: any) => f.provenance),
    note: `Effect measured at ${label(p.unit_of_effect)}. A superseded figure is one an earlier draft stated and a later draft replaced; it is kept so a citation to the older number can be traced.`,
  }] };
}

// ---------- Report cards ----------

const scoringText = (c: any) => c.scoring.map((s: any) => `${s.points} pt: ${s.label ?? s.condition} [${s.condition}]`).join('; ');
export function reportCardsIndexPage(): PageTables {
  const page = '/report-cards/';
  const r = rubrics().sort((a, b) => b.version.localeCompare(a.version))[0];
  const g = grades();
  const states = g ? [...g.states].sort((a, b) => a.name.localeCompare(b.name)) : [];
  const total = r ? r.criteria.reduce((a: number, c: any) => a + c.max_points, 0) : 0;
  const tables: DataTable[] = [];
  if (g) tables.push({
    id: 'grades', page, csv: '/report-cards/grades.csv', title: `Report card grades by state, rubric ${g.rubric_version}`,
    head: ['State', 'Market', 'Grade', 'Points', 'Available', 'Percent of available', 'Criteria entered', 'Criteria applicable', 'Inputs pending review', 'Not yet entered'],
    rows: states.map((s) => [L(s.name, `${BASE}/report-cards/${s.abbr.toLowerCase()}/`), s.market === 'regulated_market' ? 'Regulated market' : 'No regulated market', s.grade ? `${s.grade}${s.review === 'provisional' ? ' (provisional)' : ''}` : 'Incomplete', s.points, s.available, s.pct ?? '', s.criteria.filter((c) => c.status === 'scored').length, s.criteria.length, s.inputs_pending_review, s.missing_criteria.length ? s.missing_criteria.map((m) => label(m)).join(', ') : 'all entered']),
    note: 'A letter appears only when every applicable criterion has an entry; an absent record is not evidence that a protection is absent. Provisional means at least one input is pending review.',
  });
  if (r) {
    tables.push({ id: 'weights', page, title: `Points available per criterion, rubric ${r.version}`, head: ['Criterion', 'ID', 'Applies to', 'Maximum points', 'Share of total'], rows: r.criteria.map((c: any) => [c.title, c.criterion_id, label(c.applies_to), c.max_points, { text: `${Math.round((c.max_points / total) * 100)}%`, value: Math.round((c.max_points / total) * 1000) / 1000 }]) });
    tables.push({
      id: 'rubric', page, title: `Rubric version ${r.version}: criteria and scoring rows`,
      head: ['Criterion', 'ID', 'Applies to', 'Presence input', 'Scoring, first match wins', 'Max', 'Rationale', 'Evidence basis', 'Evidence note'],
      rows: r.criteria.map((c: any) => [c.title, c.criterion_id, label(c.applies_to), c.presence, scoringText(c), c.max_points, c.rationale, c.evidence_basis?.length ? c.evidence_basis.join(', ') : 'none in the research library', c.evidence_note ?? '']),
      note: `${label(r.status)}, effective ${fmtDate(r.effective_from)}. Scoring rows are tried in order and the first whose condition matches awards its points. The condition language is documented on the report cards page.`,
    });
  }
  if (g) tables.push({ id: 'inputs', page, title: 'Rubric inputs and how each is derived from the state files', head: ['Input', 'Derived from'], rows: Object.entries(g.derived_inputs).map(([k, v]) => [k, v]) });
  return { page, title: 'State report cards and scoring rubric', tables };
}

const evidenceProv = (e: GradeEvidence): Provenance => ({ source_id: e.source_id, source_url: e.source_url, archive_url: null, retrieved_at: e.retrieved_at, retrieval_method: 'see the state record', entered_by: 'see the state record', status: e.status as Provenance['status'] });
export function reportCardPage(s: StateGrade): PageTables {
  const page = `/report-cards/${s.abbr.toLowerCase()}/`;
  const r = rubrics().sort((a, b) => b.version.localeCompare(a.version))[0];
  const crit = (id: string) => r?.criteria.find((c: any) => c.criterion_id === id);
  const fmtVal = (v: unknown) => v === null || v === undefined ? 'not entered' : typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v);
  const ev = s.criteria.flatMap((c) => c.evidence.map((e) => ({ c, e })));
  return { page, title: `${s.name} report card`, tables: [
    { id: 'criteria', page, title: `${s.name}: report card criteria, inputs and points`,
      head: ['Criterion', 'ID', 'Applies to', 'Inputs', 'Matched row', 'Condition', 'Points', 'Maximum'],
      rows: s.criteria.map((c) => { const def = crit(c.criterion_id); return [def?.title ?? c.criterion_id, c.criterion_id, label(def?.applies_to), Object.entries(c.inputs).map(([k, v]) => `${k}: ${fmtVal(v)}`).join('; '), c.status === 'scored' ? c.label ?? '' : 'Not entered', c.status === 'scored' ? c.condition ?? '' : `presence input ${def?.presence ?? ''} is null`, c.status === 'scored' ? c.points ?? '' : '', c.max_points]; }),
      num: [6, 7], note: `Rubric ${grades()?.rubric_version}. Each input is derived from the state's data files as documented on the report cards page; the first scoring row whose condition matches awards its points.` },
    { id: 'evidence', page, title: `${s.name}: records behind each criterion`, head: ['Criterion', 'Publisher'],
      rows: ev.map(({ c, e }) => [crit(c.criterion_id)?.title ?? c.criterion_id, L((() => { try { return source(e.source_id).publisher; } catch { return e.source_id; } })(), e.source_url)]),
      prov: ev.map(({ e }) => evidenceProv(e)) },
  ] };
}

// ---------- Methodology: sources; data page ----------

export function sourcesPage(): PageTables {
  const page = '/methodology/sources/';
  const all = [...sources().values()];
  const groups = [['primary', 'Primary'], ['secondary', 'Secondary'], ['tertiary', 'Tertiary (never cited for a figure)']] as const;
  const types = [...new Set(all.map((s) => s.publisher_type))].sort((a, b) => all.filter((s) => s.publisher_type === b).length - all.filter((s) => s.publisher_type === a).length);
  const tier = (t: string): DataTable => ({ id: t, page, title: `${groups.find((g) => g[0] === t)![1]} sources in the registry`, head: ['Publisher', 'Title', 'Type', 'Access', 'Cadence', 'Reliability notes', 'ID'], rows: all.filter((s) => s.tier === t).map((s) => [L(s.publisher, s.url), s.title, label(s.publisher_type), label(s.access_method), s.update_cadence, s.reliability_notes ?? '', s.source_id]) });
  return { page, title: 'Source registry', tables: [
    { id: 'by-type', page, title: 'Registered sources by publisher type and tier', head: ['Publisher type', 'Primary', 'Secondary', 'Tertiary'], rows: types.map((t) => [label(t), ...groups.map(([g]) => all.filter((s) => s.publisher_type === t && s.tier === g).length)]) },
    tier('primary'), tier('secondary'), tier('tertiary'),
  ] };
}

export function dataPage(): PageTables {
  const page = '/data/';
  const rows = profiles().map((p) => { const pg = pgFunding(p.abbr); const pm = predictionMarkets(p.abbr); const r = reviewSummary([p, pg, pm].filter(Boolean)); return { p, pg, pm, r }; })
    .sort((a, b) => b.r.total - a.r.total || a.p.name.localeCompare(b.p.name));
  return { page, title: 'Data, downloads and coverage', tables: [{
    id: 'coverage', page, title: 'Provenance records per state, verified and pending review',
    head: ['State', 'Headline status', 'Profile', 'Funding file', 'Prediction markets file', 'Records', 'Verified', 'Pending review'],
    rows: rows.map(({ p, pg, pm, r }) => [L(p.name, stateHref(p)), HEADLINE_LABEL[headlineStatus(p)], p.profile_completeness === 'full' ? 'Full' : 'Status only', yesNo(!!pg), yesNo(!!pm), r.total, r.verified, r.pending]),
    note: 'A record is counted once per provenance block across the profile, funding and prediction market files.',
  }] };
}

// ---------- Everything, for the CSV endpoint ----------

let allCache: PageTables[] | null = null;
export function allPageTables(): PageTables[] {
  if (allCache) return allCache;
  allCache = [
    homePage(), statesIndexPage(), ...profiles().map(statePage), outcomesPage(),
    legislationIndexPage(), ...bills().map(billPage), researchIndexPage(), ...papers().map(paperPage),
    reportCardsIndexPage(), ...(grades()?.states ?? []).map(reportCardPage), sourcesPage(), dataPage(),
  ];
  return allCache;
}
export { MIN_POINTS };
