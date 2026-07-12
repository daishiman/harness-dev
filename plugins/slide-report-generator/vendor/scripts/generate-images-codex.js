#!/usr/bin/env node
/**
 * generate-images-codex.js
 *
 * build-image-prompts.js が生成した各 slide-{slug}.prompt.md を読み、
 * codex exec で meta.generation.size に従う16:9 PNGを生成するためのオーケストレーション。
 * 生成後 cwebp で .webp 化し、meta.json の source を実生成系(codex-image2)へ更新する。
 *
 * コスト注意:
 *   codex exec は OpenAI/codex の課金が発生する(1枚あたり概ね 1-2 分)。
 *   既定で --dry-run を使い、組み立てたコマンドと対象を必ず目視してから本実行すること。
 *
 * ============================================================================
 * 改良点(実運用事故対策 / 2026-06-26)
 *   全面画像デッキ28枚を codex exec で生成した際に起きた事故への対策を移植した。
 *
 *   [事故1] codex の内蔵 image_gen は画像を
 *           $CODEX_HOME/generated_images/<session-id>/ に保存するが、
 *           指定パスへの自動コピーが不安定で「PNG not found」-> exit 1 になった。
 *     対策: codex に保存を任せず、session dir から自前で回収する
 *           (generateAndRecover / findFreshPngInSession)。
 *
 *   [事故2] codex が画像生成に失敗し、imagegen の説明テキスト
 *           (先頭が "# Image Generation Skill" = 先頭バイト hex 23 20 49 6d 61 67 65)
 *           を .png 名で保存することがある。
 *     対策: PNG署名(先頭4バイト 89 50 4E 47)を持つファイルだけを回収する
 *           (isPngFile)。テキスト .png は除外。
 *
 *   [事故3] 従来コードは署名未確認でコピーしていた。
 *     対策: 回収時に署名確認 -> コピー後に再度署名確認(二重チェック)。
 *
 *   [事故4] 5並列だと後半グループで session-id 抽出が失敗し回収ミスが多発した。
 *     対策: codex exec の出力をログファイルにリダイレクトし stdin を閉じる
 *           (`codex exec "..." > logfile 2>&1 < /dev/null`)。
 *           $(codex exec ...) のキャプチャは session-id が取れず失敗しやすいので使わない。
 *           ログから `session id:` を grep 抽出して session dir を特定する。
 *
 *   その他:
 *     - 有効な PNG が取れなければ最大3回までリトライ(codex に再生成させる)。
 *     - webp 化(cwebp)は日本語パスで失敗する場合に備え LANG/LC_ALL を設定。
 *       cwebp が無い/失敗した場合は macOS の sips に自動フォールバック。
 *
 * メモリ実績(reference_image_gen_via_codex_exec):
 *   - codex はシェルエイリアスで --dangerously-bypass-approvals-and-sandbox 付き。
 *     フラグ二重指定は禁止。`codex exec "..."` のみを用いる。
 *   - 5枚程度ずつ並列(run_in_background)が速い。本ラッパは逐次実行+バッチ境界ログ。
 *     さらに速くしたい場合は --dry-run で出力したコマンドを Bash 側で run_in_background 並列実行してよい。
 *   - webp 化は cwebp -q 90 を直叩き(convert-to-webp.js はディレクトリ判定で空振りした実績あり)。
 *
 * 使用方法:
 *   node scripts/generate-images-codex.js <slide-dir> [--only slug,...] [--batch 5] [--dry-run] [--source codex-image2]
 *
 *   --only     対象 slug をカンマ区切りで限定。
 *   --batch    バッチサイズ(既定 5)。バッチ境界をログ出力する。
 *   --dry-run  codex を呼ばず、組み立てた codex exec コマンドと対象一覧だけ出力(コスト発生なし)。
 *   --source   meta.json に記録する source 値(既定 codex-image2)。
 *
 * 自己テスト手順(コスト発生なし):
 *   1) 構文チェック:
 *        node --check scripts/generate-images-codex.js
 *   2) dry-run で組み立てコマンドを確認(codex を呼ばない):
 *        node scripts/generate-images-codex.js <slide-dir> --dry-run
 *      期待: 各 slug の [CODEX ] 行が `codex exec '...' > <log> 2>&1 < /dev/null` 形式、
 *            フラグ二重指定なし、[WEBP ] 行に cwebp と LANG/LC_ALL が出ること。
 *   3) PNG署名判定の単体確認(本物 PNG と偽 PNG):
 *        printf '\x89PNG\r\n\x1a\n' > /tmp/real.png
 *        printf '# Image Generation Skill' > /tmp/fake.png
 *      isPngFile('/tmp/real.png') === true / isPngFile('/tmp/fake.png') === false を確認。
 *   4) LIVE は課金が発生する。1枚に限定して試す:
 *        node scripts/generate-images-codex.js <slide-dir> --only <slug>
 * ============================================================================
 */

import { existsSync, readdirSync, readFileSync, writeFileSync, statSync, openSync, readSync, closeSync, copyFileSync, mkdtempSync, rmSync } from 'fs';
import { join, basename } from 'path';
import { tmpdir, homedir } from 'os';
import { execSync } from 'child_process';

const VALUE_FLAGS = new Set(['only', 'batch', 'source']);

// PNG 署名(先頭8バイトの先頭4バイト)。テキスト .png(事故2)を弾く判定に使う。
const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47];
// 有効 PNG が取れないときの最大リトライ回数(codex に再生成させる)。
const MAX_RETRIES = 3;

function usage() {
  console.error('Usage: node scripts/generate-images-codex.js <slide-dir> [--only slug,...] [--batch 5] [--dry-run] [--source <name>]');
  process.exit(2);
}

function parseArgs(argv) {
  const flags = {};
  const positional = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const eq = arg.indexOf('=');
      if (eq !== -1) {
        flags[arg.slice(2, eq)] = arg.slice(eq + 1);
      } else {
        const name = arg.slice(2);
        if (VALUE_FLAGS.has(name)) {
          flags[name] = argv[i + 1];
          i += 1;
        } else {
          flags[name] = true;
        }
      }
    } else {
      positional.push(arg);
    }
  }
  return { flags, positional };
}

// シェル用シングルクォートエスケープ(convert-to-webp.js と同方式)
function shellQuote(value) {
  return `'${String(value).replace(/'/g, "'\\''")}'`;
}

// $CODEX_HOME を解決する(未設定時は ~/.codex)。image_gen の出力先の基点。
function codexHome() {
  return process.env.CODEX_HOME && process.env.CODEX_HOME.trim()
    ? process.env.CODEX_HOME.trim()
    : join(homedir(), '.codex');
}

// 先頭4バイトが PNG署名(89 50 4E 47)かを確認する。
// 事故2対策: imagegen の説明テキスト(先頭 "# Image" = 23 20 49 6d ...)を .png として弾く。
function isPngFile(filePath) {
  if (!existsSync(filePath)) return false;
  let fd;
  try {
    fd = openSync(filePath, 'r');
    const buf = Buffer.alloc(4);
    const bytes = readSync(fd, buf, 0, 4, 0);
    if (bytes < 4) return false;
    for (let i = 0; i < 4; i += 1) {
      if (buf[i] !== PNG_SIGNATURE[i]) return false;
    }
    return true;
  } catch {
    return false;
  } finally {
    if (fd !== undefined) {
      try { closeSync(fd); } catch { /* noop */ }
    }
  }
}

function buildCodexInstruction(promptPath, pngPath, refImages, generationSize, textPolicy) {
  // codex exec へ「prompt.md 全文を読み、imagegen(拡散モデル)で PNG を生成・保存」する単一指示を渡す。
  // 重要(実証済み): imagegen を明示強制しないと codex は PIL/matplotlib 等のコード描画に退化し、
  // 単色角丸ボックス+テキストの平坦図になる(full-image-deck-method §1.1.1 が禁止する退化パターン)。
  // 「imagegen を使え・コード描画するな・リッチなアイソメイラストにしろ」を必ず明示する。
  // 二重情報源の解消: prompt.md を画像内テキストの単一正本にし、codex 指示文と衝突したら prompt.md を優先。
  // baked-with-overlay では prompt.md が指定した短語ラベルは意図したテキストであり garbled ではない。
  const textSourceOfTruth = textPolicy === 'baked-with-overlay'
    ? 'The prompt file is the single source of truth for in-image text: render the short quoted Japanese labels it specifies crisply and undistorted; only garbled, distorted, or unintended extra text is forbidden, not the intentional baked labels.'
    : 'The prompt file is the single source of truth; if this instruction conflicts with it, follow the prompt file.';
  const instruction = [
    `Read the file ${promptPath} in full.`,
    `Render it using your built-in text-to-image image generation tool (a diffusion imagegen model such as gpt-image).`,
    `This is mandatory: do NOT draw the image programmatically with PIL/Pillow/matplotlib/cairo/numpy/SVG or any code-based drawing.`,
    `The result must be a rich, detailed manga-like isometric illustration with drawn objects, scenes, depth and soft shading,`,
    `NOT flat colored rounded boxes with text.`,
    `Resize to exactly ${generationSize} (16:9) if needed and save the final PNG to ${pngPath}.`,
    `Honor any "no people / 人物なし" and Negative constraints written in the prompt;`,
    `do not include garbled or distorted text in the image.`,
    textSourceOfTruth,
    `Output only the PNG file.`,
  ].join(' ');
  let full = instruction;
  if (refImages && refImages.length > 0) {
    full += ' Also open and view these reference images and match their visual style, palette, navy outline, isometric geometry and motif rendering: ' + refImages.join(', ') + '. Change only the subject; do not copy the reference subject; keep framing and add no extra elements.';
  }
  return full;
}

// codex exec コマンド文字列を組み立てる。
// 事故4対策: 出力をログにリダイレクトし stdin を閉じる(< /dev/null)。
//   $(codex exec ...) でキャプチャすると session-id が取れず回収に失敗しやすい。
// codex はエイリアスで --dangerously-bypass-approvals-and-sandbox 付きのため、
// フラグは一切付けず `codex exec "..."` のみ(フラグ二重指定禁止)。
function buildCodexCommand(instruction, logPath) {
  return `codex exec ${shellQuote(instruction)} > ${shellQuote(logPath)} 2>&1 < /dev/null`;
}

// webp 化コマンド。日本語パス対策に LANG/LC_ALL を UTF-8 で固定する。
function buildCwebpCommand(pngPath, webpPath) {
  return `LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 cwebp -q 90 ${shellQuote(pngPath)} -o ${shellQuote(webpPath)}`;
}

// cwebp が無い/失敗したときの macOS フォールバック。
function buildSipsCommand(pngPath, webpPath) {
  return `LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 sips -s format webp ${shellQuote(pngPath)} --out ${shellQuote(webpPath)}`;
}

function readMeta(metaPath) {
  if (!existsSync(metaPath)) return null;
  try { return JSON.parse(readFileSync(metaPath, 'utf8')); } catch (err) { return null; }
}

function generationSizeFor(meta) {
  const size = meta && meta.generation && typeof meta.generation.size === 'string'
    ? meta.generation.size
    : '2560x1440';
  return /^\d+x\d+$/.test(size) ? size : '2560x1440';
}

// styleReference(anchorSlug/refSlugs) を確定済み画像パスへ解決する。
// gpt-image-2 は seed 非対応のため、前ページ/基準ページの確定画素を参照する image-to-image が
// ページ間一貫性の決定論アンカーになる。codex はエイリアス(bypass付き)なのでフラグ追加せず、
// 参照画像パスは codex exec の指示文に明記して codex に開かせる(フラグ二重指定禁止の方針)。
// n は候補ばらつきで coherent set ではない。各ページは前ページ参照を伴う独立生成にする。
function resolveReferenceImages(generatedDir, styleReference) {
  if (!styleReference || typeof styleReference !== 'object') return [];
  const slugs = [];
  if (styleReference.anchorSlug) slugs.push(styleReference.anchorSlug);
  if (Array.isArray(styleReference.refSlugs)) styleReference.refSlugs.forEach(function (rs) { slugs.push(rs); });
  const paths = [];
  for (const s2 of slugs) {
    const webp = join(generatedDir, s2 + '.webp');
    const png = join(generatedDir, s2 + '.png');
    if (existsSync(webp)) paths.push(webp);
    else if (existsSync(png)) paths.push(png);
  }
  return paths.slice(0, 16);
}

function collectTargets(generatedDir, onlySet) {
  // Obsidian が .md を同期取り込みして消すため prompt は .prompt.txt を正とする。
  // 後方互換で既存 .prompt.md も拾い、slug で重複排除する(.txt 優先)。
  const slugs = new Set();
  for (const file of readdirSync(generatedDir)) {
    if (file.endsWith('.prompt.txt')) slugs.add(basename(file, '.prompt.txt'));
    else if (file.endsWith('.prompt.md')) slugs.add(basename(file, '.prompt.md'));
  }
  return [...slugs]
    .filter((slug) => !onlySet || onlySet.has(slug))
    .sort();
}

function updateMetaSource(metaPath, sourceName) {
  if (!existsSync(metaPath)) return false;
  let meta;
  try {
    meta = JSON.parse(readFileSync(metaPath, 'utf8'));
  } catch {
    return false;
  }
  meta.source = sourceName;
  if (!('seed' in meta)) meta.seed = null; // backend が seed を返さない限り null を維持
  writeFileSync(metaPath, `${JSON.stringify(meta, null, 2)}\n`, 'utf8');
  return true;
}

// codex exec のログから `session id:` を grep 抽出する。
// 事故4対策の核心: 並列でもログ単位で session-id が確実に取れる。
function extractSessionId(logPath) {
  if (!existsSync(logPath)) return null;
  let text;
  try { text = readFileSync(logPath, 'utf8'); } catch { return null; }
  // 例: "session id: 019f0106-dace-7de0-954c-cb65e5bfca68"
  // 大文字小文字や前後の装飾を許容し、UUID 様の文字列を拾う。
  const m = text.match(/session\s*id[:=]?\s*([0-9a-fA-F-]{8,})/i);
  return m ? m[1] : null;
}

// session dir 内で PNG署名を持つファイルを「新しい順」で1件返す(事故1+2対策)。
// テキスト .png(署名なし)は除外する。
function findFreshPngInSession(sessionDir) {
  if (!existsSync(sessionDir)) return null;
  let entries;
  try { entries = readdirSync(sessionDir); } catch { return null; }
  const candidates = entries
    .map((name) => join(sessionDir, name))
    .filter((p) => {
      try { return statSync(p).isFile(); } catch { return false; }
    })
    .filter((p) => isPngFile(p)) // 署名で本物 PNG だけに絞る
    .sort((a, b) => {
      try { return statSync(b).mtimeMs - statSync(a).mtimeMs; } catch { return 0; }
    });
  return candidates.length > 0 ? candidates[0] : null;
}

// 1 slug 分の生成+回収。成功時は pngPath を返し、失敗時は null。
// 事故1-4を踏まえた回収フロー:
//   (a) 一時ログへリダイレクト+stdin クローズで codex exec を実行
//   (b) ログから session id を抽出 -> session dir を特定
//   (c) session dir から PNG署名つきファイルを新しい順で1件回収
//   (d) pngPath へコピー -> 再度署名確認
//   (e) 有効 PNG が取れなければ最大3回までリトライ(codex に再生成させる)
function generateAndRecover(slug, instruction, pngPath) {
  const genImagesBase = join(codexHome(), 'generated_images');
  const logDir = mkdtempSync(join(tmpdir(), 'codex-img-'));
  try {
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt += 1) {
      const logPath = join(logDir, `${slug}.attempt${attempt}.log`);
      const codexCmd = buildCodexCommand(instruction, logPath);
      console.log(`  [RUN ${attempt}/${MAX_RETRIES}] ${codexCmd}`);
      try {
        execSync(codexCmd, { stdio: 'ignore' });
      } catch (error) {
        console.error(`  [WARN] codex exec exited non-zero (attempt ${attempt}): ${error.message}`);
        // 非ゼロ終了でも session dir に PNG が残っていることがあるので回収は試みる。
      }

      // (b) session id 抽出
      const sessionId = extractSessionId(logPath);
      if (!sessionId) {
        console.error(`  [WARN] session id not found in codex log (attempt ${attempt}); see ${logPath}`);
        continue;
      }
      const sessionDir = join(genImagesBase, sessionId);

      // (c) 署名つき PNG を新しい順で回収
      const srcPng = findFreshPngInSession(sessionDir);
      if (!srcPng) {
        console.error(`  [WARN] no valid PNG (signature 89 50 4E 47) in ${sessionDir} (attempt ${attempt}); likely codex emitted text-as-png. Retrying.`);
        continue;
      }

      // (d) コピー -> 再署名確認(コピー破損や取り違えを最終ガード)
      try {
        copyFileSync(srcPng, pngPath);
      } catch (error) {
        console.error(`  [WARN] copy failed ${srcPng} -> ${pngPath} (attempt ${attempt}): ${error.message}`);
        continue;
      }
      if (!isPngFile(pngPath)) {
        console.error(`  [WARN] copied file is not a valid PNG after copy (attempt ${attempt}): ${pngPath}. Retrying.`);
        continue;
      }

      console.log(`  [PNG ] recovered ${basename(srcPng)} (session ${sessionId}) -> ${basename(pngPath)} (${statSync(pngPath).size} bytes)`);
      return pngPath;
    }
    console.error(`  [FAIL] could not obtain a valid PNG for ${slug} after ${MAX_RETRIES} attempt(s)`);
    return null;
  } finally {
    try { rmSync(logDir, { recursive: true, force: true }); } catch { /* noop */ }
  }
}

// PNG -> webp。cwebp(LANG/LC_ALL付き)優先、失敗時 sips フォールバック。
function convertToWebp(pngPath, webpPath, cwebpAvailable, sipsAvailable) {
  if (cwebpAvailable) {
    try {
      execSync(buildCwebpCommand(pngPath, webpPath), { stdio: 'pipe' });
      if (existsSync(webpPath)) {
        console.log(`  [WEBP] ${basename(webpPath)} via cwebp (${statSync(webpPath).size} bytes)`);
        return true;
      }
    } catch (error) {
      console.error(`  [WARN] cwebp failed: ${error.message}`);
    }
  }
  if (sipsAvailable) {
    try {
      execSync(buildSipsCommand(pngPath, webpPath), { stdio: 'pipe' });
      if (existsSync(webpPath)) {
        console.log(`  [WEBP] ${basename(webpPath)} via sips fallback (${statSync(webpPath).size} bytes)`);
        return true;
      }
    } catch (error) {
      console.error(`  [WARN] sips fallback failed: ${error.message}`);
    }
  }
  if (!cwebpAvailable && !sipsAvailable) {
    console.error('  [WARN] neither cwebp (brew install webp) nor sips available; skipping webp conversion');
  }
  return false;
}

function main() {
  const { flags, positional } = parseArgs(process.argv.slice(2));
  const slideDir = positional[0];
  if (!slideDir) usage();

  const generatedDir = join(slideDir, 'assets', 'generated');
  if (!existsSync(generatedDir)) {
    console.error(`FAIL: not found: ${generatedDir}`);
    process.exit(1);
  }

  const onlySet = flags.only
    ? new Set(String(flags.only).split(',').map((s) => s.trim()).filter(Boolean))
    : null;
  const batchSize = Math.max(1, parseInt(flags.batch || '5', 10) || 5);
  const dryRun = Boolean(flags['dry-run']);
  const sourceName = flags.source ? String(flags.source) : 'codex-image2';

  const slugs = collectTargets(generatedDir, onlySet);
  if (slugs.length === 0) {
    console.error('FAIL: no *.prompt.txt (or legacy *.prompt.md) targets found (run build-image-prompts.js first, or check --only)');
    process.exit(1);
  }

  console.log(`Targets: ${slugs.length} slide(s), batch size ${batchSize}`);
  console.log(`Codex generated_images base: ${join(codexHome(), 'generated_images')}`);
  if (dryRun) {
    console.log('Mode: DRY-RUN (codex is NOT called; no cost incurred)');
  } else {
    console.log('Mode: LIVE (codex exec WILL run and incur OpenAI/codex cost)');
  }
  console.log('---');

  let cwebpAvailable = false;
  let sipsAvailable = false;
  if (!dryRun) {
    try { execSync('which cwebp', { stdio: 'pipe' }); cwebpAvailable = true; } catch { cwebpAvailable = false; }
    try { execSync('which sips', { stdio: 'pipe' }); sipsAvailable = true; } catch { sipsAvailable = false; }
  }

  let produced = 0;
  for (let i = 0; i < slugs.length; i += batchSize) {
    const batch = slugs.slice(i, i + batchSize);
    const batchNo = Math.floor(i / batchSize) + 1;
    console.log(`Batch ${batchNo}: ${batch.join(', ')}`);

    for (const slug of batch) {
      const promptTxt = join(generatedDir, `${slug}.prompt.txt`);
      const promptPath = existsSync(promptTxt) ? promptTxt : join(generatedDir, `${slug}.prompt.md`);
      const pngPath = join(generatedDir, `${slug}.png`);
      const webpPath = join(generatedDir, `${slug}.webp`);
      const metaPath = join(generatedDir, `${slug}.meta.json`);
      const meta = readMeta(metaPath);
      const refImages = resolveReferenceImages(generatedDir, meta && meta.styleReference);
      if (meta && meta.styleReference && refImages.length === 0) {
        console.log('  [WARN  ] ' + slug + ': styleReference set but anchor image(s) not yet generated; generate anchorSlug first, then re-run. Proceeding without reference.');
      }
      if (dryRun && meta && meta.generation) {
        console.log('  [GEN   ] expected model=' + meta.generation.modelSnapshot + ' quality=' + meta.generation.quality + ' size=' + meta.generation.size + ' (gpt-image-2 has no seed; reproducibility via prompt invariance + reference images)');
      }
      const generationSize = generationSizeFor(meta);
      const instruction = buildCodexInstruction(promptPath, pngPath, refImages, generationSize, meta && meta.textPolicy);

      if (dryRun) {
        // dry-run のログパスは実体に依存しない代表値(実行時は一時ディレクトリに作る)。
        const sampleLog = join(tmpdir(), `codex-img-XXXX/${slug}.attempt1.log`);
        if (refImages.length > 0) console.log('  [REFS  ] ' + refImages.join(', '));
        console.log(`  [TARGET] ${slug} -> ${pngPath}`);
        console.log(`  [CODEX ] ${buildCodexCommand(instruction, sampleLog)}`);
        console.log('  [RECOV ] grep "session id:" from log -> $CODEX_HOME/generated_images/<session-id>/ -> pick newest PNG with signature 89 50 4E 47 (retry up to ' + MAX_RETRIES + ')');
        console.log(`  [WEBP  ] ${buildCwebpCommand(pngPath, webpPath)}`);
        console.log(`  [WEBP* ] fallback: ${buildSipsCommand(pngPath, webpPath)}`);
        continue;
      }

      // LIVE 実行: codex exec はユーザー課金が発生する。
      const recovered = generateAndRecover(slug, instruction, pngPath);
      if (!recovered) {
        // 回収失敗。次の slug へ(全体は止めない)。
        continue;
      }

      // webp 化(cwebp 直叩き / sips フォールバック)。コピーした PNG は署名済み。
      if (!existsSync(webpPath)) {
        convertToWebp(pngPath, webpPath, cwebpAvailable, sipsAvailable);
      }

      // meta.source を実生成系へ更新
      if (updateMetaSource(metaPath, sourceName)) {
        console.log(`  [META] source=${sourceName} recorded for ${slug}`);
      }
      produced += 1;
    }
  }

  console.log('---');
  if (dryRun) {
    console.log(`DRY-RUN done: ${slugs.length} command(s) prepared (no images generated, no cost).`);
  } else {
    console.log(`LIVE done: ${produced}/${slugs.length} image(s) generated. Validate with:`);
    console.log(`  node scripts/validate-ai-image-assets.js ${slideDir} --strict-style-genome --check-genome-content`);
  }
}

main();
