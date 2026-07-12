#!/usr/bin/env node
/**
 * スライド検証スクリプト（16:9対応版）
 *
 * v7.5.0: captureScreenshots を is-active 方式に書き換え。
 *   旧 translateX 方式は .slider__item が position:absolute + opacity:0
 *   + visibility:hidden で実装されているため機能せず、全スライドが空白で
 *   撮影される致命的バグがあった。
 *
 * 機能:
 * - 全スライドのスクリーンショットを撮影（16:9ビューポート）
 * - 16:9アスペクト比の検証
 * - 問題のあるスライドを特定（テキスト切れ、改行問題など）
 * - 検証完了後のスクリーンショット削除
 *
 * 使用方法:
 *   node scripts/verify-slides.js <html-file-path> [output-dir] [options]
 *
 * オプション:
 *   --cleanup       スクリーンショットを削除して終了
 *   --auto-cleanup  検証後に自動でスクリーンショットを削除
 *   --check-ratio   16:9アスペクト比のみチェック（スクリーンショットなし）
 *
 * 例:
 *   node scripts/verify-slides.js ./index.html ./screenshots
 *   node scripts/verify-slides.js ./index.html --cleanup
 *   node scripts/verify-slides.js ./index.html --auto-cleanup
 *   node scripts/verify-slides.js ./index.html --check-ratio
 */

import { spawnSync } from 'child_process';
import { existsSync, mkdirSync, readdirSync, rmSync } from 'fs';
import { dirname, join } from 'path';
import { parseArgs, hasFlag, VIEWPORT, EXIT_CODES, getDirname } from './utils.js';

const __dirname = getDirname(import.meta.url);

// コマンドライン引数のパース
const { flags, positional } = parseArgs();

const cleanupOnly = hasFlag(flags, 'cleanup');
const autoCleanup = hasFlag(flags, 'auto-cleanup');
const checkRatioOnly = hasFlag(flags, 'check-ratio');
const htmlPath = positional[0];
const outputDir = positional[1] || (htmlPath ? join(dirname(htmlPath), 'screenshots') : null);

// 16:9基準解像度（utils.jsから）
const VIEWPORT_WIDTH = VIEWPORT.WIDTH;
const VIEWPORT_HEIGHT = VIEWPORT.HEIGHT;
const ASPECT_RATIO = VIEWPORT.ASPECT_RATIO;

// ヘルプ表示
if (hasFlag(flags, 'help', 'h')) {
  console.log(`
スライド検証スクリプト（16:9対応版）

使用方法:
  node verify-slides.js <html-file-path> [output-dir] [options]

オプション:
  --cleanup       指定ディレクトリのスクリーンショットを削除して終了
  --auto-cleanup  検証完了後に自動でスクリーンショットを削除
  --check-ratio   16:9アスペクト比のみチェック（スクリーンショットなし）
  --help, -h      このヘルプを表示

例:
  # スクリーンショット撮影（16:9ビューポート: 1920x1080）
  node verify-slides.js ./index.html ./screenshots

  # スクリーンショット削除のみ
  node verify-slides.js ./index.html --cleanup

  # 撮影後に自動削除
  node verify-slides.js ./index.html --auto-cleanup

  # 16:9アスペクト比の検証のみ
  node verify-slides.js ./index.html --check-ratio
`);
  process.exit(EXIT_CODES.SUCCESS);
}

/**
 * スクリーンショットディレクトリを削除
 */
function cleanupScreenshots(dir) {
  if (!dir) {
    console.error('❌ 削除対象のディレクトリが指定されていません');
    return false;
  }

  const absoluteDir = dir.startsWith('/') ? dir : join(process.cwd(), dir);

  if (!existsSync(absoluteDir)) {
    console.log(`⚠️  ディレクトリが存在しません: ${absoluteDir}`);
    return true;
  }

  try {
    const files = readdirSync(absoluteDir).filter(f => f.endsWith('.png'));

    if (files.length === 0) {
      console.log(`📁 削除対象のスクリーンショットがありません: ${absoluteDir}`);
      return true;
    }

    // スクリーンショットファイルを削除
    files.forEach(file => {
      const filePath = join(absoluteDir, file);
      rmSync(filePath);
    });

    console.log(`🗑️  ${files.length}枚のスクリーンショットを削除しました`);

    // ディレクトリが空なら削除
    const remaining = readdirSync(absoluteDir);
    if (remaining.length === 0) {
      rmSync(absoluteDir, { recursive: true });
      console.log(`📁 空のディレクトリを削除: ${absoluteDir}`);
    }

    return true;
  } catch (error) {
    console.error(`❌ 削除中にエラーが発生: ${error.message}`);
    return false;
  }
}

/**
 * 16:9アスペクト比を検証
 */
function checkAspectRatio(htmlPath) {
  if (!htmlPath) {
    console.error('Usage: node verify-slides.js <html-file-path> --check-ratio');
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!existsSync(htmlPath)) {
    console.error(`Error: HTML file not found: ${htmlPath}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  const absoluteHtmlPath = htmlPath.startsWith('/') ? htmlPath : join(process.cwd(), htmlPath);

  console.log('📐 16:9アスペクト比を検証中...');
  console.log(`   HTML: ${absoluteHtmlPath}`);
  console.log(`   基準解像度: ${VIEWPORT_WIDTH}x${VIEWPORT_HEIGHT} (16:9)`);

  const pythonScript = `
from playwright.sync_api import sync_playwright
import sys
import json

html_path = "${absoluteHtmlPath}"

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': ${VIEWPORT_WIDTH}, 'height': ${VIEWPORT_HEIGHT}})
        page.goto(f"file://{html_path}")
        page.wait_for_timeout(1500)

        # 16:9検証
        result = page.evaluate("""
            () => {
                const slideArea = document.querySelector('.slide-area');
                const sliderContainer = document.querySelector('.slider__container');
                const sliderItems = document.querySelectorAll('.slider__item');

                const checks = {
                    hasSlideArea: !!slideArea,
                    slideAreaSize: slideArea ? { width: slideArea.offsetWidth, height: slideArea.offsetHeight } : null,
                    slideAreaRatio: slideArea ? (slideArea.offsetWidth / slideArea.offsetHeight).toFixed(4) : null,
                    expectedRatio: (16/9).toFixed(4),
                    ratioMatch: false,
                    cssVariables: {
                        slideMaxWidth: getComputedStyle(document.documentElement).getPropertyValue('--slide-max-width').trim(),
                        slideMaxHeight: getComputedStyle(document.documentElement).getPropertyValue('--slide-max-height').trim(),
                    },
                    slideItemsCount: sliderItems.length,
                    slideItemsHaveAspectRatio: Array.from(sliderItems).every(item =>
                        getComputedStyle(item).aspectRatio.includes('16') || getComputedStyle(item).aspectRatio === 'auto'
                    )
                };

                if (slideArea) {
                    const ratio = slideArea.offsetWidth / slideArea.offsetHeight;
                    checks.ratioMatch = Math.abs(ratio - (16/9)) < 0.01;
                }

                return checks;
            }
        """)

        print(json.dumps(result, indent=2, ensure_ascii=False))

        browser.close()

        # 結果判定
        if not result['hasSlideArea']:
            print("\\n❌ 検証失敗: .slide-area要素が見つかりません")
            sys.exit(1)
        elif not result['ratioMatch']:
            print(f"\\n❌ 検証失敗: アスペクト比が16:9ではありません")
            print(f"   実際: {result['slideAreaRatio']} / 期待: {result['expectedRatio']}")
            sys.exit(1)
        else:
            print(f"\\n✅ 検証成功: 16:9アスペクト比が正しく設定されています")
            print(f"   スライドエリア: {result['slideAreaSize']['width']}x{result['slideAreaSize']['height']}px")
            sys.exit(0)

except Exception as e:
    print(f"❌ エラー: {e}")
    sys.exit(1)
`;

  try {
    const result = spawnSync('python3', ['-c', pythonScript], {
      stdio: 'inherit',
      timeout: 60000
    });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`python3 exited with ${result.status}`);
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * スクリーンショットを撮影（16:9対応）
 */
function captureScreenshots(htmlPath, outputDir) {
  if (!htmlPath) {
    console.error('Usage: node verify-slides.js <html-file-path> [output-dir]');
    console.error('Example: node verify-slides.js ./index.html ./screenshots');
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!existsSync(htmlPath)) {
    console.error(`Error: HTML file not found: ${htmlPath}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  // 絶対パスに変換
  const absoluteHtmlPath = htmlPath.startsWith('/') ? htmlPath : join(process.cwd(), htmlPath);
  const absoluteOutputDir = outputDir.startsWith('/') ? outputDir : join(process.cwd(), outputDir);

  // 出力ディレクトリ作成
  if (!existsSync(absoluteOutputDir)) {
    mkdirSync(absoluteOutputDir, { recursive: true });
  }

  console.log('🔍 スライド検証を開始（16:9モード）...');
  console.log(`   HTML: ${absoluteHtmlPath}`);
  console.log(`   出力: ${absoluteOutputDir}`);
  console.log(`   ビューポート: ${VIEWPORT_WIDTH}x${VIEWPORT_HEIGHT} (16:9)`);

  // Pythonスクリプトを生成して実行
  const pythonScript = `
from playwright.sync_api import sync_playwright
import os
import sys

html_path = "${absoluteHtmlPath}"
output_dir = "${absoluteOutputDir}"

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 16:9ビューポートを使用
        page = browser.new_page(viewport={'width': ${VIEWPORT_WIDTH}, 'height': ${VIEWPORT_HEIGHT}})
        page.goto(f"file://{html_path}")
        page.wait_for_timeout(2000)

        # 16:9検証
        slide_area = page.evaluate("document.querySelector('.slide-area')")
        if slide_area:
            area_info = page.evaluate("""
                () => {
                    const area = document.querySelector('.slide-area');
                    return { width: area.offsetWidth, height: area.offsetHeight };
                }
            """)
            ratio = area_info['width'] / area_info['height']
            expected = 16/9
            if abs(ratio - expected) < 0.01:
                print(f"📐 16:9検証OK: {area_info['width']}x{area_info['height']}px")
            else:
                print(f"⚠️  16:9警告: 比率が {ratio:.4f} です（期待値: {expected:.4f}）")
        else:
            print("⚠️  .slide-area要素が見つかりません（旧形式の可能性）")

        # 総スライド数を取得
        total = page.evaluate("document.querySelectorAll('.slider__item').length")
        print(f"📊 総スライド数: {total}")

        # 可視テキストの型崩れを検証
        bad_text = page.evaluate("""
            () => {
                const text = document.body.innerText || '';
                const patterns = ['[object Object]', '[render error:'];
                return patterns.filter((p) => text.includes(p));
            }
        """)
        if bad_text:
            print(f"❌ 可視テキストの型崩れを検出: {', '.join(bad_text)}")
            sys.exit(1)

        # slide-areaの幅を取得（なければビューポート幅）
        slide_width = page.evaluate("""
            () => {
                const area = document.querySelector('.slide-area');
                return area ? area.offsetWidth : window.innerWidth;
            }
        """)

        # v7.5.0: is-active 方式に対応（translateX 方式は .slider__item が
        # position:absolute + opacity:0 + visibility:hidden のため機能しない）
        # 1枚ずつ .is-active を付け替え、可視化されたスライドを撮影する
        for i in range(total):
            clip = page.evaluate(f"""
                () => {{
                    const items = document.querySelectorAll('.slider__item');
                    items.forEach((it, idx) => {{
                        if (idx === {i}) it.classList.add('is-active');
                        else it.classList.remove('is-active');
                    }});
                    // クリップ領域は .slide-area（無ければ .is-active）
                    const target = document.querySelector('.slide-area') ||
                                   document.querySelector('.slider__item.is-active');
                    if (!target) return null;
                    const r = target.getBoundingClientRect();
                    return {{ x: r.x, y: r.y, width: r.width, height: r.height }};
                }}
            """)
            page.wait_for_timeout(220)
            if clip and clip['width'] > 10 and clip['height'] > 10:
                page.screenshot(
                    path=f"{output_dir}/slide_{i+1:02d}.png",
                    clip={'x': clip['x'], 'y': clip['y'],
                          'width': clip['width'], 'height': clip['height']}
                )
            else:
                page.screenshot(path=f"{output_dir}/slide_{i+1:02d}.png")
            print(f"   ✅ スライド {i+1}/{total}")

        browser.close()
        print(f"\\n🎉 完了: {output_dir}")
        sys.exit(0)
except Exception as e:
    print(f"❌ エラー: {e}")
    sys.exit(1)
`;

  try {
    const result = spawnSync('python3', ['-c', pythonScript], {
      stdio: 'inherit',
      timeout: 300000 // 5分タイムアウト
    });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`python3 exited with ${result.status}`);

    // スクリーンショット数を確認
    const screenshots = readdirSync(absoluteOutputDir).filter(f => f.endsWith('.png'));
    console.log(`\n📁 ${screenshots.length}枚のスクリーンショットを保存`);

    return true;
  } catch (error) {
    console.error('スクリーンショット撮影に失敗しました');
    console.error('Playwrightがインストールされているか確認してください:');
    console.error('  pip install playwright && playwright install chromium');
    return false;
  }
}

// メイン処理
if (cleanupOnly) {
  // 削除のみモード
  console.log('🗑️  スクリーンショット削除モード');
  const targetDir = outputDir || (htmlPath ? join(dirname(htmlPath), 'screenshots') : null);
  const success = cleanupScreenshots(targetDir);
  process.exit(success ? EXIT_CODES.SUCCESS : EXIT_CODES.ERROR);
} else if (checkRatioOnly) {
  // 16:9検証のみモード
  console.log('📐 16:9アスペクト比検証モード');
  const success = checkAspectRatio(htmlPath);
  process.exit(success ? EXIT_CODES.SUCCESS : EXIT_CODES.VALIDATION_FAILED);
} else {
  // 通常モード: スクリーンショット撮影（16:9対応）
  const success = captureScreenshots(htmlPath, outputDir);

  if (success && autoCleanup) {
    // 自動削除モード
    console.log('\n⏳ 3秒後にスクリーンショットを自動削除します...');
    console.log('   （中断するには Ctrl+C）\n');

    setTimeout(() => {
      cleanupScreenshots(outputDir);
      console.log('\n✨ 検証と削除が完了しました');
    }, 3000);
  } else if (success) {
    // 通常モード: 削除方法を案内
    console.log('\n💡 次のステップ:');
    console.log('   1. スクリーンショットを確認してレイアウト問題を特定');
    console.log('   2. 問題のあるスライドのHTMLを修正');
    console.log('   3. 再度このスクリプトを実行して検証');
    console.log('\n📐 16:9アスペクト比のみを検証する場合:');
    console.log(`   node verify-slides.js ${htmlPath} --check-ratio`);
    console.log('\n🗑️  確認完了後、以下のコマンドでスクリーンショットを削除:');
    console.log(`   node verify-slides.js ${htmlPath} --cleanup`);
  } else {
    process.exit(EXIT_CODES.ERROR);
  }
}
