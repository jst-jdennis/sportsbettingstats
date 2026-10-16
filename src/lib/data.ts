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
export interface PredictionMarkets { fips: string; as_of: string; review_note?: string | null; operating_platforms: any[]; state_actions: any[]; litigation: any[] }
export interface Bill { slug: string; fips: string; session: string; bill_number: string; title: string; market_segment: string[]; summary: string; would?: string[] | null; sponsors?: any[] | null; status: string; status_date?: string | null; actions?: any[] | null; votes?: any[] | null; text_url?: string | null; legislature_page_url?: string | null; fiscal_note_url?: string | null; fiscal_estimate_text?: string | null; notes?: string | null; provenance: Provenance }
export interface Paper { slug: string; title: string; authors: string[]; year_first_circulated: number; publication_status: string; venue?: string | null; doi?: string | null; canonical_url?: string | null; market_segment: string; unit_of_effect: string; data_used?: string | null; design?: string | null; plain_language_summary: string; methodology_notes?: string[] | null; limitations?: string[] | null; versions: any[]; key_figures: any[]; citations_in_policy?: any[] | null; provenance: Provenance }
export interface Rubric { version: string; status: string; effective_from: string; preamble?: string | null; criteria: any[]; grade_bands: any[]; no_market_rule: string }

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
function readYaml<T>(p: string): T { return applyMerges(yamlLoad(fs.readFileSync(p, 'utf8'))) as T; }
function readCsv<T = Record<string, string>>(p: string): T[] { return parse(fs.readFileSync(p, 'utf8'), { columns: true, skip_empty_lines: true }) as T[]; }

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
