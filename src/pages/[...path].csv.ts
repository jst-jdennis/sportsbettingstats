// One endpoint serves every table and chart on the site as CSV, at the table's
// page path plus its id (for example /states/nj/legal-status.csv), and every
// page's tables together in long format at <page>/data.csv. The rows come from
// the same registry the pages render, so a download always matches the page.
import type { APIRoute } from 'astro';
import { allPageTables } from '../lib/pageTables';
import { toCsv, pageCsv, csvPath, checkTables } from '../lib/tables';

const CSV = { 'Content-Type': 'text/csv; charset=utf-8' };

export function getStaticPaths() {
  const out: { params: { path: string }; props: { page: string; id: string | null } }[] = [];
  for (const pg of allPageTables()) {
    checkTables(pg);
    for (const t of pg.tables) {
      if (t.csv) continue; // served by its own endpoint already
      out.push({ params: { path: csvPath(t).replace(/^\//, '').replace(/\.csv$/, '') }, props: { page: pg.page, id: t.id } });
    }
    if (pg.tables.length) out.push({ params: { path: `${pg.page}data`.replace(/^\//, '') }, props: { page: pg.page, id: null } });
  }
  return out;
}

export const GET: APIRoute = ({ props }) => {
  const { page, id } = props as { page: string; id: string | null };
  const pg = allPageTables().find((x) => x.page === page);
  if (!pg) return new Response('not found', { status: 404 });
  if (id === null) return new Response(pageCsv(pg), { headers: CSV });
  const t = pg.tables.find((x) => x.id === id);
  return t ? new Response(toCsv(t), { headers: CSV }) : new Response('not found', { status: 404 });
};
