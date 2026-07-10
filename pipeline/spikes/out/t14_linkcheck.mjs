// T-14: dist内の全内部hrefが /investsite プレフィックス付きかつリンク先ファイルが実在するかを機械検証する使い捨てスクリプト。
// 実行: node pipeline/spikes/out/t14_linkcheck.mjs (site/dist ビルド後に実行すること)
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const distDir = join(process.cwd(), "site", "dist");
const BASE = "/investsite";

function walk(dir) {
  let files = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      files = files.concat(walk(full));
    } else if (entry.endsWith(".html")) {
      files.push(full);
    }
  }
  return files;
}

const htmlFiles = walk(distDir);
let errors = [];
let checkedLinks = 0;

for (const file of htmlFiles) {
  const html = readFileSync(file, "utf-8");
  const hrefs = [...html.matchAll(/href="([^"]*)"/g)].map((m) => m[1]);
  for (const href of hrefs) {
    if (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("#") || href.startsWith("mailto:")) {
      continue; // 外部リンク・アンカーはスコープ外
    }
    checkedLinks++;
    if (!href.startsWith(BASE)) {
      errors.push(`[NO_BASE_PREFIX] ${file}: href="${href}"`);
      continue;
    }
    // ローカルファイル存在確認: /investsite/factors/value/ -> dist/factors/value/index.html
    const relPath = href.slice(BASE.length); // "/factors/value/"
    let targetPath;
    if (relPath === "" || relPath === "/") {
      targetPath = join(distDir, "index.html");
    } else if (relPath.endsWith("/")) {
      targetPath = join(distDir, relPath, "index.html");
    } else if (relPath.match(/\.[a-z0-9]+$/i)) {
      targetPath = join(distDir, relPath); // favicon.svg 等の静的アセット
    } else {
      targetPath = join(distDir, relPath + "/index.html");
    }
    if (!existsSync(targetPath)) {
      errors.push(`[MISSING_TARGET] ${file}: href="${href}" -> ${targetPath}`);
    }
  }
}

console.log(`HTMLファイル数: ${htmlFiles.length}`);
console.log(`検査した内部リンク数: ${checkedLinks}`);
if (errors.length > 0) {
  console.log(`エラー: ${errors.length}件`);
  for (const e of errors) console.log(e);
  process.exit(1);
} else {
  console.log("エラー: 0件(全内部リンクが /investsite プレフィックス付きかつリンク先実在)");
}
