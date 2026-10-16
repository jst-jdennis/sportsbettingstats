// Renders the state map to static SVG at build time. No client JavaScript.
import { geoAlbersUsa, geoPath } from 'd3-geo';
import { feature } from 'topojson-client';
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);

const topo = JSON.parse(fs.readFileSync(require.resolve('us-atlas/states-10m.json'), 'utf8'));
const statesFc: any = feature(topo, topo.objects.states);

export interface MapDatum { fips: string; abbr: string; name: string; cls: string; title: string; href: string }

export function renderMap(data: MapDatum[], width = 960, height = 600): string {
  const projection = geoAlbersUsa().fitSize([width, height], statesFc);
  const pathGen = geoPath(projection);
  const byFips = new Map(data.map((d) => [d.fips, d]));
  const parts: string[] = [];
  for (const f of statesFc.features) {
    const fips = String(f.id).padStart(2, '0');
    const d = byFips.get(fips);
    const dPath = pathGen(f);
    if (!dPath || !d) continue;
    parts.push(`<a href="${d.href}" class="st ${d.cls}" aria-label="${esc(d.name)}: ${esc(d.title)}"><path d="${dPath}"><title>${esc(d.name)}: ${esc(d.title)}</title></path></a>`);
  }
  // Labels for small states are rendered in the legend/table, not on the map, to stay legible.
  const labels: string[] = [];
  for (const f of statesFc.features) {
    const fips = String(f.id).padStart(2, '0');
    const d = byFips.get(fips);
    if (!d) continue;
    const area = pathGen.area(f);
    if (area < 1800) continue;
    const [x, y] = pathGen.centroid(f);
    if (!isFinite(x)) continue;
    labels.push(`<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" class="lbl" aria-hidden="true">${d.abbr}</text>`);
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="map-title map-desc" class="usmap"><title id="map-title">Legal status of sports wagering by state</title><desc id="map-desc">Choropleth map. Each state links to its profile page. The same information is in the table below the map.</desc>${parts.join('')}${labels.join('')}</svg>`;
}
function esc(s: string): string { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
