/**
 * withBase — サイトの base パス(GitHub Pages のプロジェクトPages配信: /investsite/)を
 * 考慮したサイト内リンク生成ヘルパー。
 *
 * astro.config.mjs の base 設定により import.meta.env.BASE_URL が
 * 本番: "/investsite/"、ローカル開発時(base未設定相当): "/" になる。
 * コンポーネント側は常にルート相対パス("/factors/" 等)を渡し、このヘルパーで
 * base を前置してから <a href> に渡すこと。
 *
 * @param path - "/" から始まるサイト内絶対パス(例: "/factors/value/")
 * @returns base を前置したパス(例: "/investsite/factors/value/")。外部URLはそのまま呼ばないこと。
 */
export function withBase(path: string): string {
  const base = import.meta.env.BASE_URL ?? "/";
  const baseNoTrailingSlash = base === "/" ? "" : base.replace(/\/$/, "");
  return `${baseNoTrailingSlash}${path}`;
}
