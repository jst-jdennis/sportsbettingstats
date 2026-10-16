import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// GitHub Pages project site. Change `site` and `base` together when moving
// to a custom domain (base becomes '/').
export default defineConfig({
  site: 'https://jst-jdennis.github.io',
  base: '/sportsbettingstats',
  trailingSlash: 'always',
  output: 'static',
  integrations: [sitemap()],
  build: { format: 'directory' },
});
