// Build-time data access. Reads the version-controlled files under data/
// and exposes typed accessors. Nothing here touches the network.
import fs from 'node:fs';
import path from 'node:path';
import { load as yamlLoad } from 'js-yaml';
import { parse } from 'csv-parse/sync';
import { execSync } from 'node:child_process';

const ROOT = path.resolve(process.cwd());
const DATA = path.join(ROOT, 'data');

export type Status = 'verified' | 'pending_review' | 'unverified' | 'disputed' | 'superseded';
export interface Provenance {
  source_id: string;
  source_url: string;
  archive_url?: string | null;
  retrieved_at: string;
  retrieval_method: string;
  transform?: string | null;
  entered_by: string;
  reviewed_by?: string | null;
  status: Status;
  page_or_table?: string | null;
  notes?: string | null;
}
export interface Source {
  source_id: string; publisher: string; publisher_type: string; title: string; url: string;
  access_method: string; update_cadence: string; license?: string | null; reliability_notes?: string | null;
  tier: 'primary' | 'secondary' | 'tertiary'; fips?: string | null;
}
export interface LegalStatusRow {
  market_segment: string; channel: 'retail' | 'online';
  scope: string; status: string; authorized_on?: string | null; launched_on?: string | null;
  authority?: { type: string; citation: string; url?: string | null } | null;
  operator_model?: string | null; notes?: string | null; provenance: Provenance;
}
export interface StateProfile {
  fips: string; abbr: string; name: string; profile_completeness?: 'full' | 'status_only'; summary?: string | null;
  legal_status: LegalStatusRow[];
  regulators: { name: string; url?: string | null; type: string; roles: string[]; provenance: Provenance }[];
  legal_age?: { age: number; scope: string; authority_citation?: string | null; provenance: Provenance }[] | null;
  tax?: any[] | null;
  consumer_protections?: any | null;
  limitations?: string[] | null;
}
export interface PgFunding { fips: string; records: any[] }
export interface PrevalenceRate { measure: string; definition: string; value_pct: number; ci_low_pct?: number | null; ci_high_pct?: number | null; denominator?: string | null; provenance: Provenance }
export interface PrevalenceStudy { study_id: string; fips: string; title: string; authors?: string[] | null; commissioned_by?: string | null; conducted_by: string; published_at?: string | null; fieldwork_year: number; fieldwork_start?: string | null; fieldwork_end?: string | null; instrument: string; instrument_note?: string | null; sample_size?: number | null; population: string; mode: string; margin_of_error_pct_points?: number | null; rates: PrevalenceRate[]; report_url: string; comparability_note: string; limitations?: string | null; provenance: Provenance }
export interface PrevalenceSearch { fips: string; searched_on: string; searched_by: string; scope: string; found: boolean; candidates?: { title: string; year?: number | null; url: string; note?: string | null }[] | null; notes?: string | null }
export interface PredictionMarkets { fips: string; as_of: string; review_note?: string | null; operating_platforms: any[]; state_actions: any[]; litigation: any[] }
export interface Bill { slug: string; fips: string; session: string; bill_number: string; title: string; market_segment: string[]; summary: string; would?: string[] | null; sponsors?: any[] | null; status: string; status_date?: string | null; actions?: any[] | null; votes?: any[] | null; text_url?: string | null; legislature_page_url?: string | null; fiscal_note_url?: string | null; fiscal_estimate_text?: string | null; notes?: string | null; provenance: Provenance }
export interface Paper { slug: string; title: string; authors: string[]; year_first_circulated: number; publication_status: string; venue?: string | null; doi?: string | null; canonical_url?: string | null; market_segment: string; unit_of_effect: string; data_used?: string | null; design?: string | null; plain_language_summary: string; methodology_notes?: string[] | null; limitations?: string[] | null; versions: any[]; key_figures: any[]; citations_in_policy?: any[] | null; provenance: Provenance }
export interface GradeEvidence { source_id: string; source_url: string; retrieved_at: string; status: string }
export interface GradeCriterion { criterion_id: string; max_points: number; inputs: Record<string, unknown>; evidence: GradeEvidence[]; status: 'scored' | 'not_entered'; points: number | null; label: string | null; condition: string | null }
export interface StateGrade { fips: string; abbr: string; name: string; market: 'regulated_market' | 'no_regulated_market'; profile_completeness: string | null; criteria: GradeCriterion[]; points: number; available: number; points_entered: number; pct: number | null; grade: string | null; status: 'complete' | 'incomplete'; review: 'verified' | 'provisional' | null; inputs_pending_review: number; missing_criteria: string[] }
export interface Grades { rubric_version: string; rubric_status: string; effective_from: string; data_fingerprint: string; derived_inputs: Record<string, string>; summary: { states: number; graded: number; incomplete: number; no_regulated_market: number; grades: Record<string, number> }; states: StateGrade[] }
export interface Rubric { version: string; status: string; effective_from: string; preamble?: string | null; inputs_note?: string | null; criteria: any[]; grade_bands: any[]; no_market_rule: string; incomplete_rule: string; provisional_rule: string }

// js-yaml 5 does not apply YAML merge keys (<<), while PyYAML does. Apply them
// here so both halves of the toolchain read the data files identically.
function applyMerges(node: any): any {
  if (Array.isArray(node)) return node.map(applyMerges);
  if (node && typeof node === 'object') {
    let out: Record<string, any> = {};
    if ('<<' in node) {
      const m = node['<<'];
      for (const src of Array.isArray(m) ? m : [m]) Object.assign(out, applyMerges(src));
    }
    for (const [k, v] of Object.entries(node)) if (k !== '<<') out[k] = applyMerges(v);
    return out;
  }
  return node;
}
// FIPS codes with a leading zero must stay strings. PyYAML keeps them; js-yaml
// turns an unquoted 08 into 8. Coerce every `fips` key so both agree.
function coerceFips(node: any): any {
  if (Array.isArray(node)) return node.map(coerceFips);
  if (node && typeof node === 'object') {
    for (const [k, v] of Object.entries(node)) node[k] = k === 'fips' && v != null ? String(v).padStart(2, '0') : coerceFips(v);
  }
  return node;
}
function readYaml<T>(p: string): T { return coerceFips(applyMerges(yamlLoad(fs.readFileSync(p, 'utf8')))) as T; }
// Data files do not change during a build, so each CSV is parsed once and the parsed rows are shared.
// Callers filter or copy before sorting; nothing mutates the cached array.
const _csvCache = new Map<string, unknown[]>();
function readCsv<T = Record<string, string>>(p: string): T[] {
  let rows = _csvCache.get(p);
  if (!rows) {
    rows = parse(fs.readFileSync(p, 'utf8'), { columns: true, skip_empty_lines: true }) as unknown[];
    _csvCache.set(p, rows);
  }
  return rows as T[];
}

let _sources: Map<string, Source> | null = null;
export function sources(): Map<string, Source> {
  if (!_sources) {
    const doc = readYaml<{ sources: Source[] }>(path.join(DATA, 'sources', 'sources.yaml'));
    _sources = new Map(doc.sources.map((s) => [s.source_id, s]));
  }
  return _sources;
}
export function source(id: string): Source {
  const s = sources().get(id);
  if (!s) throw new Error(`Unknown source_id ${id}. The validator should have caught this.`);
  return s;
}

export function states(): { fips: string; abbr: string; name: string; census_region: string }[] {
  return readCsv(path.join(DATA, 'reference', 'states.csv'));
}
export function population(): { fips: string; year: string; population: string; vintage: string; status: Status; source_id: string; source_url: string; retrieved_at: string; notes?: string }[] {
  return readCsv(path.join(DATA, 'reference', 'population.csv')) as any;
}

let _profiles: StateProfile[] | null = null;
export function profiles(): StateProfile[] {
  if (!_profiles) {
    const dir = path.join(DATA, 'states');
    _profiles = fs.readdirSync(dir)
      .filter((d) => fs.existsSync(path.join(dir, d, 'profile.yaml')))
      .map((d) => readYaml<StateProfile>(path.join(dir, d, 'profile.yaml')))
      .sort((a, b) => a.name.localeCompare(b.name));
  }
  return _profiles;
}
export function profile(abbr: string): StateProfile | undefined { return profiles().find((p) => p.abbr === abbr.toUpperCase()); }
export function pgFunding(abbr: string): PgFunding | null {
  const p = path.join(DATA, 'states', abbr.toLowerCase(), 'pg_funding.yaml');
  return fs.existsSync(p) ? readYaml<PgFunding>(p) : null;
}
export function predictionMarkets(abbr: string): PredictionMarkets | null {
  const p = path.join(DATA, 'states', abbr.toLowerCase(), 'prediction_markets.yaml');
  return fs.existsSync(p) ? readYaml<PredictionMarkets>(p) : null;
}
export function prevalenceStudies(fips?: string): PrevalenceStudy[] {
  const p = path.join(DATA, 'outcomes', 'prevalence_studies.yaml');
  if (!fs.existsSync(p)) return [];
  return readYaml<{ studies: PrevalenceStudy[] }>(p).studies.filter((s) => !fips || s.fips === fips).sort((a, b) => a.fieldwork_year - b.fieldwork_year || (a.fieldwork_start ?? '').localeCompare(b.fieldwork_start ?? ''));
}
/** The latest recorded search for prevalence studies in a state, or null when none has been logged. */
export function prevalenceSearch(fips: string): PrevalenceSearch | null {
  const p = path.join(DATA, 'outcomes', 'prevalence_studies.yaml');
  if (!fs.existsSync(p)) return null;
  const all = (readYaml<{ searches?: PrevalenceSearch[] }>(p).searches ?? []).filter((s) => s.fips === fips).sort((a, b) => a.searched_on.localeCompare(b.searched_on));
  return all[all.length - 1] ?? null;
}
export function bills(): Bill[] {
  const dir = path.join(DATA, 'legislation', 'bills');
  return fs.readdirSync(dir).filter((f) => f.endsWith('.yaml')).map((f) => readYaml<Bill>(path.join(dir, f)))
    .sort((a, b) => (b.status_date ?? '').localeCompare(a.status_date ?? ''));
}
export function papers(): Paper[] {
  const dir = path.join(DATA, 'research', 'papers');
  return fs.readdirSync(dir).filter((f) => f.endsWith('.yaml')).map((f) => readYaml<Paper>(path.join(dir, f)))
    .sort((a, b) => a.year_first_circulated - b.year_first_circulated || a.slug.localeCompare(b.slug));
}
let _grades: Grades | null = null;
/** The committed grades file for the highest rubric version. scripts/grade.py --check keeps it equal to a fresh computation. */
export function grades(): Grades | null {
  if (_grades) return _grades;
  const dir = path.join(DATA, 'report_cards', 'grades');
  if (!fs.existsSync(dir)) return null;
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json')).sort();
  if (!files.length) return null;
  _grades = JSON.parse(fs.readFileSync(path.join(dir, files[files.length - 1]), 'utf8')) as Grades;
  return _grades;
}
export function gradeFor(abbr: string): StateGrade | null { return grades()?.states.find((s) => s.abbr === abbr.toUpperCase()) ?? null; }
export function rubrics(): Rubric[] {
  const dir = path.join(DATA, 'report_cards', 'rubric');
  return fs.readdirSync(dir).filter((f) => f.endsWith('.yaml')).map((f) => readYaml<Rubric>(path.join(dir, f)));
}

// ---------- Derived values (never stored) ----------

export type HeadlineStatus = 'none' | 'retail_only' | 'online_only' | 'retail_and_online' | 'authorized_not_launched';
export const HEADLINE_LABEL: Record<HeadlineStatus, string> = {
  none: 'No legal sports wagering',
  retail_only: 'Retail only',
  online_only: 'Online only',
  retail_and_online: 'Retail and online',
  authorized_not_launched: 'Authorized, not launched',
};

/** Headline classification used on the map. Rule is published on the methodology page. */
export function headlineStatus(p: StateProfile): HeadlineStatus {
  const live = (ch: 'retail' | 'online') => p.legal_status.some((r) => r.channel === ch && r.status === 'live');
  const authorized = p.legal_status.some((r) => r.status === 'authorized_not_launched');
  const r = live('retail'), o = live('online');
  if (r && o) return 'retail_and_online';
  if (r) return 'retail_only';
  if (o) return 'online_only';
  if (authorized) return 'authorized_not_launched';
  return 'none';
}

/** Scope qualifiers that matter for honest labeling (tribal-only, on-premises mobile). */
export function scopeQualifiers(p: StateProfile): string[] {
  const q: string[] = [];
  const live = p.legal_status.filter((r) => r.status === 'live');
  if (live.length && live.every((r) => r.scope === 'tribal_lands_only')) q.push('tribal lands only');
  else if (live.some((r) => r.channel === 'retail' && r.scope === 'tribal_lands_only')) q.push('retail on tribal lands only');
  if (live.some((r) => r.channel === 'online' && r.scope === 'on_premises_only')) q.push('mobile only on licensed premises');
  if (live.some((r) => r.channel === 'retail' && r.scope === 'lottery_kiosk')) q.push('lottery kiosks');
  return q;
}

export function earliestLaunch(p: StateProfile): string | null {
  const d = p.legal_status.map((r) => r.launched_on).filter((x): x is string => !!x).sort();
  return d[0] ?? null;
}

/** Collect every provenance block under an object. */
export function collectProvenance(obj: any, out: Provenance[] = []): Provenance[] {
  if (Array.isArray(obj)) obj.forEach((x) => collectProvenance(x, out));
  else if (obj && typeof obj === 'object') {
    if (obj.provenance && typeof obj.provenance === 'object') out.push(obj.provenance);
    for (const k of Object.keys(obj)) if (k !== 'provenance') collectProvenance(obj[k], out);
  }
  return out;
}
export function asOf(objs: any[]): string {
  const dates = objs.flatMap((o) => collectProvenance(o)).map((p) => p.retrieved_at).filter(Boolean).sort();
  return dates[dates.length - 1] ?? '';
}
export function reviewSummary(objs: any[]): { total: number; verified: number; pending: number } {
  const all = objs.flatMap((o) => collectProvenance(o));
  return { total: all.length, verified: all.filter((p) => p.status === 'verified').length, pending: all.filter((p) => p.status !== 'verified').length };
}

let _commit: string | null = null;
export function commitHash(): string {
  if (_commit === null) {
    try { _commit = execSync('git rev-parse --short HEAD', { cwd: ROOT }).toString().trim(); } catch { _commit = 'unknown'; }
  }
  return _commit;
}
export const BUILD_DATE = new Date().toISOString().slice(0, 10);

export function fmtDate(d?: string | null): string {
  if (!d) return 'not entered';
  const [y, m, day] = d.split('-').map(Number);
  if (!m) return String(y);
  const dt = new Date(Date.UTC(y, m - 1, day || 1));
  return dt.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: day ? 'numeric' : undefined, timeZone: 'UTC' });
}
export function pct(x?: number | null): string { return x == null ? 'not entered' : `${(x * 100).toFixed(x * 100 % 1 ? 2 : 0)}%`; }
export function label(s?: string | null): string { return s ? s.replace(/_/g, ' ') : 'not entered'; }

// ---------- Derived series for charts (computed at build, never stored) ----------

/** Research figures that carry a numeric value and are current and not unverified, with their paper. */
export function effectFigures(): { paper: Paper; fig: any }[] {
  const out: { paper: Paper; fig: any }[] = [];
  for (const paper of papers()) for (const fig of paper.key_figures) {
    if (fig.value_numeric == null || fig.status !== 'current') continue;
    if (fig.provenance.status === 'unverified' || fig.provenance.status === 'superseded') continue;
    out.push({ paper, fig });
  }
  return out;
}

export const OUTCOME_LABEL: Record<string, string> = {
  bankruptcy: 'Bankruptcy filings', credit_score: 'Credit scores', debt_collections: 'Debt in collections', loan_delinquency: 'Loan delinquency',
  savings_investment: 'Saving and investing', consumer_debt: 'Consumer debt', help_seeking: 'Help-seeking', intimate_partner_violence: 'Intimate partner violence',
  problem_gambling_prevalence: 'Problem gambling prevalence', betting_participation: 'Betting participation', other: 'Other',
};

/** Number of states with a live channel at the end of each year, from the first legal wager to the current year. */
export function adoptionByYear(): { year: number; any: number; online: number; retail: number }[] {
  const ps = profiles();
  const first = (p: StateProfile, ch?: 'retail' | 'online') => p.legal_status.filter((r) => (!ch || r.channel === ch) && r.launched_on).map((r) => r.launched_on!).sort()[0] ?? null;
  const starts = ps.map((p) => first(p)).filter((x): x is string => !!x).sort();
  if (!starts.length) return [];
  const y0 = Number(starts[0].slice(0, 4)), y1 = Number(BUILD_DATE.slice(0, 4));
  const out = [];
  for (let y = y0; y <= y1; y++) {
    const cutoff = `${y}-12-31`;
    const count = (ch?: 'retail' | 'online') => ps.filter((p) => { const d = first(p, ch); return d && d <= cutoff; }).length;
    out.push({ year: y, any: count(), online: count('online'), retail: count('retail') });
  }
  return out;
}

// ---------- Outcome time series (Phase 2) ----------
// CSV rows as written by the ingestion layer. Files may not exist yet; readers return [].

export interface SeriesProv { source_id: string; source_url: string; archive_url: string; retrieved_at: string; status: Status; entered_by: string; reviewed_by: string; notes: string }
export interface HandleRevenueRow extends SeriesProv { fips: string; period_start: string; period_end: string; channel: 'retail' | 'online' | 'all'; market_segment: string; handle_usd: string; gross_revenue_usd: string; adjusted_revenue_usd: string; promo_deductions_usd: string; state_tax_usd: string; revenue_definition: string; is_revised: string }
export interface BankruptcyRow extends SeriesProv { fips: string; period_start: string; period_end: string; measure: 'quarter' | 'twelve_months_ending'; chapter: string; filings: string }
export interface HelplineRow extends SeriesProv { fips: string; period_start: string; period_end: string; contact_type: string; contacts: string; operator: string; counting_rule: string }

const _outcomeCache = new Map<string, unknown[]>();
function readOutcomeCsv<T>(name: string): T[] {
  let rows = _outcomeCache.get(name);
  if (!rows) {
    const p = path.join(DATA, 'outcomes', name);
    rows = fs.existsSync(p) ? (readCsv<T>(p) as any[]).filter((r) => r.status !== 'superseded') : [];
    _outcomeCache.set(name, rows);
  }
  return rows as T[];
}
export function handleRevenue(fips?: string): HandleRevenueRow[] { return readOutcomeCsv<HandleRevenueRow>('handle_revenue.csv').filter((r) => !fips || r.fips === fips).sort((a, b) => a.period_start.localeCompare(b.period_start)); }
export function bankruptcy(fips?: string): BankruptcyRow[] { return readOutcomeCsv<BankruptcyRow>('bankruptcy.csv').filter((r) => !fips || r.fips === fips).sort((a, b) => a.period_start.localeCompare(b.period_start)); }
export function helpline(fips?: string): HelplineRow[] { return readOutcomeCsv<HelplineRow>('helpline.csv').filter((r) => !fips || r.fips === fips).sort((a, b) => a.period_start.localeCompare(b.period_start)); }

/** Population for a state in a given year, falling back to the nearest available year. Returns the row so the vintage can be cited. */
export function populationFor(fips: string, year: number) {
  const rows = population().filter((r) => r.fips === fips && r.status !== 'superseded');
  if (!rows.length) return null;
  return rows.sort((a, b) => Math.abs(Number(a.year) - year) - Math.abs(Number(b.year) - year) || Number(b.vintage) - Number(a.vintage))[0];
}

/** Filings per 100,000 residents, computed at build and never stored. */
export function per100k(count: number, fips: string, year: number): { value: number; pop: ReturnType<typeof populationFor> } | null {
  const pop = populationFor(fips, year);
  if (!pop) return null;
  return { value: (count / Number(pop.population)) * 100000, pop };
}

/** Legalization markers for a state's charts: first legal wager per channel, from the profile. */
export function legalizationMarkers(p: StateProfile): { date: string; label: string }[] {
  return p.legal_status.filter((r) => r.launched_on && r.status === 'live').map((r) => ({ date: r.launched_on as string, label: `First ${r.channel} wager` })).sort((a, b) => a.date.localeCompare(b.date));
}

/** Summary of a series before and after a date: means over the window, with counts, for the pre/post table. Descriptive only. */
export function prePost(points: { date: string; value: number }[], cut: string, windowMonths = 24) {
  const d = new Date(cut + 'T00:00:00Z');
  const lo = new Date(d); lo.setUTCMonth(lo.getUTCMonth() - windowMonths);
  const hi = new Date(d); hi.setUTCMonth(hi.getUTCMonth() + windowMonths);
  const pre = points.filter((x) => new Date(x.date + 'T00:00:00Z') >= lo && x.date < cut);
  const post = points.filter((x) => x.date >= cut && new Date(x.date + 'T00:00:00Z') < hi);
  const mean = (xs: typeof pre) => xs.length ? xs.reduce((a, x) => a + x.value, 0) / xs.length : null;
  return { pre: { n: pre.length, mean: mean(pre) }, post: { n: post.length, mean: mean(post) }, windowMonths };
}
