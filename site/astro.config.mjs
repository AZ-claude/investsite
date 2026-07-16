// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
// カスタムドメイン(invest.rakusetsu.com)公開のため base: '/' (ルート配信)。
// 内部リンクは site/src/lib/url.ts の withBase() で base を前置すること。
export default defineConfig({
  site: 'https://invest.rakusetsu.com',
  base: '/',
});
