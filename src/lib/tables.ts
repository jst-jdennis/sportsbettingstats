// Tables as data. Every table and chart on the site is declared once as a
// DataTable (see pageTables.ts); the page renders it as HTML, the catch-all
// CSV endpoint renders the same object as a file, and the fact sheets read the
// same rows. There is no second copy of any column list, so the CSV a reader
// downloads cannot drift from the table they saw.
import type { Provenance, SeriesProv } from './data';
import { source, commitHash, BUILD_DATE, fmtDate } from './data';
import { SITE } from '../site.config';

/** A cell is plain text or a number, or text with a link and a muted second line. */
export type Cell = string | number | null | undefined | { text: string; href?: string | null; meta?: string | null; value?: string | number | null };

export interface DataTable {
  /** Slug, unique within the page; the CSV is served at `${page}${id}.csv`. */
  id: string;
  /** Site-relative page path with leading and trailing slash, for example `/states/nj/`. */
  page: string;
  title: string;
  head: string[];
  rows: Cell[][];
  /** One provenance block per row. Adds a Source column in HTML and the provenance columns in CSV. */
  prov?: (Provenance | null | undefined)[];
  /** Definitional note carried into the CSV header and shown under the table. */
  note?: string | null;
  /** Latest retrieval date among the rows, when known. */
  asOf?: string | null;
  /** Zero-based indexes of numeric columns, right-aligned in HTML. Numbers are detected automatically. */
  num?: number[];
  /** Explicit CSV path when the table is already served by a dedicated endpoint, for example `/states/status.csv`. */
  csv?: string;
}

export interface PageTables { page: string; title: string; tables: DataTable[]; factsheet?: boolean }

const BASE = (import.meta.env.BASE_URL ?? '/').replace(/\/$/, '');
const ORIGIN = (import.meta.env.SITE as string | undefined) ?? 'https://jst-jdennis.github.io';

export const cellText = (c: Cell): string => c == null ? '' : typeof c === 'object' ? c.text : String(c);
export const cellMeta = (c: Cell): string | null => c != null && typeof c === 'object' ? c.meta ?? null : null;
export const cellHref = (c: Cell): string | null => c != null && typeof c === 'object' ? c.href ?? null : null;
/** The link as a CSV reader needs it: site-relative links become absolute, external links pass through. */
export const cellUrl = (c: Cell): string => { const h = cellHref(c); return !h ? '' : /^[a-z]+:/i.test(h) ? h : new URL(h, ORIGIN).toString(); };
/** What the CSV writes: the machine value when the cell carries one (a raw number, an ISO date), else the displayed text. */
export const cellValue = (c: Cell): string | number => c != null && typeof c === 'object' && c.value != null ? c.value : cellText(c);
/** Columns where any cell links somewhere get a sibling URL column in the CSV, so no link is lost in the download. */
export function linkColumns(t: DataTable): number[] { return t.head.map((_, j) => j).filter((j) => t.rows.some((r) => cellHref(r[j]))); }

/** Site-relative CSV path for a table, without the deployment base. */
export function csvPath(t: DataTable): string { return t.csv ?? `${t.page}${t.id}.csv`; }
/** Href usable in a page, with the deployment base. */
export function csvHref(t: DataTable): string { return BASE + csvPath(t); }
export function pageDataCsvHref(page: string): string { return `${BASE}${page}data.csv`; }
export function absoluteUrl(sitePath: string): string { return new URL((BASE + sitePath).replace(/\/+/g, '/'), ORIGIN).toString(); }

/** Provenance block for a row of one of the outcome CSV series, whose provenance columns are flat. */
export function seriesProv(r: SeriesProv): Provenance {
  return { source_id: r.source_id, source_url: r.source_url, archive_url: r.archive_url || null, retrieved_at: r.retrieved_at, retrieval_method: 'ingest', entered_by: r.entered_by, reviewed_by: r.reviewed_by || null, status: r.status, notes: r.notes || null };
}

/** Latest retrieval date across a table's provenance, or null. */
export function tableAsOf(t: DataTable): string | null {
  if (t.asOf) return t.asOf;
  const d = (t.prov ?? []).map((p) => p?.retrieved_at).filter((x): x is string => !!x).sort();
  return d[d.length - 1] ?? null;
}

export const PROV_COLS = ['source_id', 'source_publisher', 'source_url', 'archive_url', 'retrieved_at', 'review_status', 'source_note'] as const;
export function provCells(p: Provenance | null | undefined): string[] {
  if (!p) return PROV_COLS.map(() => '');
  let publisher = p.source_id;
  try { publisher = source(p.source_id).publisher; } catch { /* unregistered id: keep the id */ }
  return [p.source_id, publisher, p.source_url, p.archive_url ?? '', p.retrieved_at, p.status, [p.page_or_table, p.notes].filter(Boolean).join('; ')];
}

function q(v: unknown): string {
  const s = v == null ? '' : String(v);
  return /[",\r\n]/.test(s) || /^\s|\s$/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
const oneLine = (s: string) => s.replace(/\s+/g, ' ').trim();

/** Comment lines that open every CSV: what it is, where it came from, how to cite it. Readers skip lines starting with #. */
function header(title: string, page: string, asOf: string | null, note?: string | null): string[] {
  const url = absoluteUrl(page);
  const lines = [
    `# ${SITE.name}: ${oneLine(title)}`,
    `# Page: ${url}`,
    `# Built ${BUILD_DATE} from commit ${commitHash()}.${asOf ? ` Data as of ${asOf}.` : ''} License ${SITE.dataLicense.name} (${SITE.dataLicense.url}). Every row that carries a source has source_url, retrieved_at and review_status columns; pending_review means entered with a citation and not yet checked by a second reviewer.`,
  ];
  if (note) lines.push(`# Note: ${oneLine(note)}`);
  lines.push(`# Cite: ${SITE.name}. "${oneLine(title)}." ${url} (data as of ${asOf ?? BUILD_DATE}, commit ${commitHash()}, accessed ${BUILD_DATE}).`);
  return lines;
}

/** The table as CSV: header comments, column row, data rows, provenance columns when present. */
export function toCsv(t: DataTable): string {
  const links = new Set(linkColumns(t));
  const cols = t.head.flatMap((h, j) => links.has(j) ? [h, `${h} URL`] : [h]);
  const lines = header(t.title, t.page, tableAsOf(t), t.note);
  lines.push([...cols, ...(t.prov ? PROV_COLS : [])].map(q).join(','));
  t.rows.forEach((r, i) => {
    const cells = r.flatMap((c, j) => links.has(j) ? [cellValue(c), cellUrl(c)] : [cellValue(c)]);
    lines.push([...cells, ...(t.prov ? provCells(t.prov[i]) : [])].map(q).join(','));
  });
  return lines.join('\n') + '\n';
}

/** Every table on a page in one long-format file: one line per cell, with the row's provenance beside it. */
export function pageCsv(pg: PageTables): string {
  const asOf = pg.tables.map(tableAsOf).filter((x): x is string => !!x).sort().pop() ?? null;
  const lines = header(`${pg.title}, every table on the page in long format`, pg.page, asOf, 'One line per cell. table is the table id (its own CSV is at <page>/<table>.csv), row is 1-based within that table, column is the column header.');
  lines.push(['table', 'row', 'column', 'value', 'url', ...PROV_COLS].map(q).join(','));
  for (const t of pg.tables) t.rows.forEach((r, i) => {
    const pc = t.prov ? provCells(t.prov[i]) : PROV_COLS.map(() => '');
    r.forEach((c, j) => lines.push([t.id, i + 1, t.head[j] ?? '', cellValue(c), cellUrl(c), ...pc].map(q).join(',')));
  });
  return lines.join('\n') + '\n';
}

/** Build-time consistency checks: ids are slugs and unique within a page, every row matches the header width. */
export function checkTables(pg: PageTables): void {
  const seen = new Set<string>();
  for (const t of pg.tables) {
    if (!/^[a-z0-9][a-z0-9-]*$/.test(t.id)) throw new Error(`${pg.page}: table id "${t.id}" is not a slug`);
    if (t.id === 'data') throw new Error(`${pg.page}: table id "data" is reserved for the page's long-format file`);
    if (seen.has(t.id)) throw new Error(`${pg.page}: duplicate table id "${t.id}"`);
    seen.add(t.id);
    if (t.page !== pg.page) throw new Error(`${pg.page}: table "${t.id}" declares page ${t.page}`);
    t.rows.forEach((r, i) => { if (r.length !== t.head.length) throw new Error(`${pg.page} ${t.id}: row ${i + 1} has ${r.length} cells for ${t.head.length} columns`); });
    if (t.prov && t.prov.length !== t.rows.length) throw new Error(`${pg.page} ${t.id}: ${t.prov.length} provenance entries for ${t.rows.length} rows`);
  }
}

/** Convenience: index a page's tables by id, throwing on a missing one so a typo fails the build instead of rendering nothing. */
export function byId(pg: PageTables): Record<string, DataTable> & { get(id: string): DataTable } {
  const m: Record<string, DataTable> = Object.fromEntries(pg.tables.map((t) => [t.id, t]));
  return Object.assign(m, { get(id: string) { const t = m[id]; if (!t) throw new Error(`${pg.page}: no table "${id}"`); return t; } });
}

// ---------- Cell helpers: what the page shows, with the raw value for the CSV ----------
/** A date cell: long form on the page, ISO in the CSV. */
export function D(d?: string | null): Cell { return d ? { text: fmtDate(d), value: d } : ''; }
/** A money cell: formatted dollars on the page, the raw number in the CSV. */
export function USD(v?: string | number | null, empty = ''): Cell { if (v === '' || v == null) return empty; const n = Number(v); return { text: `${n < 0 ? '-' : ''}$${Math.abs(n).toLocaleString()}`, value: n }; }
/** A count cell: grouped digits on the page, the raw number in the CSV. */
export function N(v?: string | number | null, empty = ''): Cell { if (v === '' || v == null) return empty; const n = Number(v); return { text: n.toLocaleString(), value: n }; }
/** A rate cell: fixed decimals on the page, the full number in the CSV. */
export function R(v?: number | null, digits = 1, empty = ''): Cell { return v == null ? empty : { text: v.toFixed(digits), value: v }; }
/** A linked cell. */
export function L(text: string, href?: string | null, meta?: string | null): Cell { return { text, href: href ?? null, meta: meta ?? null }; }
