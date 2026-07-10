// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
// GitHub Pages(プロジェクトPages)公開のため base: '/investsite' を配下に配信する(T-14)。
// 内部リンクは site/src/lib/url.ts の withBase() で base を前置すること。
export default defineConfig({
  site: 'https://az-claude.github.io',
  base: '/investsite',
});
