#!/usr/bin/env node
/**
 * validate-report-layout.js — 記事 (report) の実描画レイアウト契約。
 *
 * スライドと記事は媒体としての契約が違うので、検査器も分ける。
 *   スライド: 固定面に 1 枚が収まりきる。縦に溢れたら負け (validate-slide-layout.js)
 *   記事:     縦スクロールは正当。負けるのは「横に溢れる」「行が長すぎる」
 *             「図が小さすぎて読めない」「見出しがどちらの段落に属するか分からない」
 * よって L1-L6 をそのまま流用せず、読み物としての可読性を R1-R6 で見る。
 *
 *   R1 重なり     見出し・本文・図解が互いに重ならない
 *   R2 横はみ出し 要素が本文コンテナの外へ出ない (= 横スクロールが生まれない)
 *   R3 行長       本文 1 行が全角 20-50 字 (日本語の可読域)
 *   R4 図解の幅   図解がコンテナ幅の 55% 以上ある (記事では横幅が読みやすさの主資源)
 *   R5 見出しの近接 見出しの上の余白 > 下の余白 (近接の原則。逆だと帰属を読み違える)
 *   R6 切れ       overflow:hidden の中で内容が切れていない
 *
 * 使い方:
 *   node scripts/validate-report-layout.js <report.html> [--viewport 1440x900] [--strict]
 * 既定 viewport は デスクトップ / ノート / タブレット縦 / A4 印刷相当 の 4 種。
 *
 * exit 0 = error 0 件、exit 1 = error あり。
 */
'use strict';

const path = require('path');
const fs = require('fs');

const PLUGIN_ROOT = path.dirname(__dirname);
const VENDOR = path.join(PLUGIN_ROOT, 'vendor');

// border-radius や字形のはみ出しを重なりと誤認しないための余裕。
const OVERLAP_TOLERANCE = 2;
// 行長の可読域 (全角換算)。目標は 40 字 (--report-measure: 40em) で、上下に
// font-size のばらつき分の幅を持たせる。上限 45 を超えると視線を左端へ戻したとき
// 次行の頭を見失いやすく、下限 24 を割ると 1 文が細切れになって主述が繋がらない。
const CPL_TARGET = 40;
const CPL_MIN = 24;
const CPL_MAX = 45;
// 行長を測る対象から外す閾値。コンテナ幅のこれ未満は見出し添えやキャプションで、
// 本文の組版として測る対象ではない。
const BODY_WIDTH_RATIO = 0.5;
// 図解がコンテナ幅のこれ未満だと、記事の中で細部が潰れて読めない。
const MIN_FIGURE_WIDTH_RATIO = 0.55;
// 図解の幅を問わない画面幅。これ未満はモバイルで、縮むのは不可避。
const NARROW_VIEWPORT = 600;
// 行送りのある要素は descender のぶん scrollHeight が常に数 px 大きい。
const CLIP_SLACK = 12;

const SEVERITY = {
  // 重なりと横はみ出しは誤検知しにくく、読めなくなる直接の原因。
  R1: 'error',
  R2: 'error',
  // 切れは overflow:hidden に限って見ているので、鳴ったら本物。
  R6: 'error',
  // 行長・図解幅・近接は「読みにくい」であって「読めない」ではない。意図的に
  // 外す意匠がありうるので、生成を止めずに人へ知らせる。
  R3: 'warning',
  R4: 'warning',
  R5: 'warning',
  // 追従ナビの不在・非追従は「読める」が「辿れない」。ブログ・読み物として
  // 成立しなくなるので error に寄せたいが、狭画面では意図的に静的へ落とす
  // 意匠 (@media max-width:900px) があるため warning に留める。
  R7: 'warning',
  // 追従 UI が本文を覆う/占有しすぎるのは「読めない」側。ただし覆いは 1px の
  // 誤差でも鳴りうるので、生成を止めずに人へ知らせる。
  R8: 'warning',
};

/** 追従 UI (ヘッダー + 目次) が占めてよい画面の縦割合の上限 (%)。
 *  到達性のための UI が本文の面積を奪ってしまう転倒を防ぐ。 */
const NAV_OCCUPANCY_MAX = 25;

/** 既定 viewport。A4 は @page margin 18mm を引いた実本文幅で測る。 */
const DEFAULT_VIEWPORTS = [
  { width: 1440, height: 900, media: 'screen', label: 'デスクトップ' },
  { width: 1024, height: 768, media: 'screen', label: 'ノート' },
  { width: 768, height: 1024, media: 'screen', label: 'タブレット縦' },
  // A4 210mm - margin 18mm×2 = 174mm ≒ 658px (96dpi)
  { width: 658, height: 1123, media: 'print', label: 'A4印刷' },
];

function parseViewports(argv) {
  const out = [];
  argv.forEach((a, i) => {
    if (a === '--viewport' && argv[i + 1]) {
      const m = /^(\d+)x(\d+)$/.exec(argv[i + 1]);
      if (m) out.push({ width: Number(m[1]), height: Number(m[2]), media: 'screen', label: 'custom' });
    }
  });
  return out.length ? out : DEFAULT_VIEWPORTS;
}

function overlapArea(a, b, tolerance) {
  const w = Math.min(a.right, b.right) - Math.max(a.left, b.left) - tolerance;
  const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) - tolerance;
  return (w > 0 && h > 0) ? Math.round(w * h) : 0;
}

/**
 * ブラウザ側で記事 1 本ぶんの実測値を集める。
 * この関数は page.evaluate でシリアライズされて別 realm で動くため、Node 側の
 * 定数はスコープに入らない。使う値は必ず引数で渡す (直接参照すると
 * ReferenceError になるが、短絡評価で到達しない間は表面化せず気付けない)。
 */
function collectReport(opts) {
  const { clipSlack } = opts;
  const box = (el) => {
    const b = el.getBoundingClientRect();
    return {
      left: b.left, top: b.top, right: b.right, bottom: b.bottom,
      width: b.width, height: b.height,
    };
  };
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (Number(cs.opacity) === 0) return false;
    const b = el.getBoundingClientRect();
    return b.width > 1 && b.height > 1;
  };

  // 本文コンテナ。はみ出し・幅比率はすべてこれを基準に測る。
  const container = document.querySelector('.report') || document.querySelector('main') || document.body;
  const cbox = box(container);

  const sections = [...document.querySelectorAll('.report-section, section, article')].filter(visible);
  const scope = sections.length ? sections : [container];

  const measured = scope.map((sec, i) => {
    const pick = (sel, role) => [...sec.querySelectorAll(sel)]
      .filter(visible)
      // 図解の中のテキストは組版の対象ではない
      .filter((e) => !e.closest('svg'))
      .map((e) => ({ role, text: (e.textContent || '').trim().slice(0, 24), ...box(e) }));

    const heads = pick('h1,h2,h3,h4', '見出し');
    const bodies = [...sec.querySelectorAll('p, li')].filter(visible)
      .filter((e) => !e.closest('svg'))
      // 入れ子の li > p を二重に数えない
      .filter((e) => !e.parentElement.closest('p'))
      .map((e) => ({
        role: '本文',
        text: (e.textContent || '').trim().slice(0, 24),
        fontSize: parseFloat(getComputedStyle(e).fontSize) || 16,
        ...box(e),
      }));
    // Mermaid / D3 は自分のマウント要素の中へ svg を生成するので、素朴に集めると
    // 器と中身の 2 つが「図解」として数えられ、必ず重なって見える。入れ子は
    // 最も外側だけを 1 つの図解として扱う。
    const figSel = 'svg, img, .mermaid, .d3-mount';
    const figs = [...sec.querySelectorAll(figSel)].filter(visible)
      .filter((e) => !e.parentElement.closest(figSel))
      .map((e) => ({ role: '図解', text: '', ...box(e) }));

    // 切れ: overflow:hidden の中でだけ見る。記事の縦スクロールは正当なので
    // それ以外の scrollHeight 超過は問題ではない。
    const clipped = [...sec.querySelectorAll('*')].filter(visible).filter((e) => {
      if (e.namespaceURI !== 'http://www.w3.org/1999/xhtml') return false;
      if (e.closest('svg')) return false;
      const cs = getComputedStyle(e);
      const hiddenY = cs.overflowY === 'hidden' || cs.overflow === 'hidden';
      const hiddenX = cs.overflowX === 'hidden' || cs.overflow === 'hidden';
      return (hiddenY && e.scrollHeight - e.clientHeight > clipSlack)
        || (hiddenX && e.scrollWidth - e.clientWidth > clipSlack);
    }).slice(0, 3).map((e) => ({
      tag: e.tagName.toLowerCase(),
      cls: (typeof e.className === 'string' ? e.className : '').split(/\s+/)[0],
      over: Math.max(e.scrollHeight - e.clientHeight, e.scrollWidth - e.clientWidth),
    }));

    return {
      index: i + 1,
      title: (sec.querySelector('h2, h1, h3') || {}).textContent
        ? (sec.querySelector('h2, h1, h3').textContent || '').trim().slice(0, 20) : `section${i + 1}`,
      heads, bodies, figs, clipped,
    };
  });

  // 見出しの近接は「文書のフロー」で測る。見出しは節の先頭に来るので、節の内側
  // だけを見ると上の比較対象 (前の節の末尾) が常に取れず、この検査は一度も
  // 発火しない。よって節をまたいだ 1 本の並びを作ってから前後を取る。
  // 実余白を getBoundingClientRect で測るのは、margin collapse があるため
  // computed style の margin が見た目の間隔と一致しないから。
  const flow = [...container.querySelectorAll(
    '.report-section, .report-section > *, .report > h1, .report > h2, .report > p',
  )].filter(visible).filter((e) => !e.classList.contains('report-section'));
  const proximity = [];
  flow.forEach((el, i) => {
    if (!/^H[1-4]$/.test(el.tagName)) return;
    const prev = flow[i - 1];
    const next = flow[i + 1];
    // 直前が見出し (h2 直後の h3 など) は「見出しの連なり」で近接の対象外
    if (!prev || !next || /^H[1-4]$/.test(prev.tagName)) return;
    const me = box(el);
    proximity.push({
      text: (el.textContent || '').trim().slice(0, 20),
      gapAbove: Math.round(me.top - box(prev).bottom),
      gapBelow: Math.round(box(next).top - me.bottom),
    });
  });

  return {
    container: cbox,
    docScrollWidth: document.documentElement.scrollWidth,
    winWidth: window.innerWidth,
    sections: measured,
    proximity,
  };
}

async function run() {
  const argv = process.argv.slice(2);
  const target = argv.find((a) => !a.startsWith('--') && !/^\d+x\d+$/.test(a));
  const strict = argv.includes('--strict');
  const viewports = parseViewports(argv);
  if (!target) {
    console.error('usage: validate-report-layout.js <report.html> [--viewport WxH] [--strict]');
    process.exit(2);
  }
  const file = path.resolve(target);
  if (!fs.existsSync(file)) {
    console.error(`ERROR [R0] ${target}: ファイルが無い`);
    process.exit(1);
  }

  const { configurePluginLocalPlaywright } = require(path.join(VENDOR, 'scripts', 'playwright-runtime.js'));
  configurePluginLocalPlaywright();
  const { chromium } = require(path.join(VENDOR, 'node_modules', 'playwright'));

  let errors = 0;
  let warnings = 0;
  const report = (code, where, message) => {
    const sev = SEVERITY[code] || 'error';
    if (sev === 'error') errors++; else warnings++;
    console.error(`${sev.toUpperCase()} [${code}] ${where}: ${message}`);
  };

  const browser = await chromium.launch();
  try {
    for (const vp of viewports) {
      const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
      if (vp.media === 'print') await page.emulateMedia({ media: 'print' });
      await page.goto(`file://${file}`);
      // Mermaid など遅延描画があるので、レイアウトが落ち着くまで待つ
      await page.waitForTimeout(600);
      const r = await page.evaluate(collectReport, { clipSlack: CLIP_SLACK });
      const vpName = `${path.basename(file)} ${vp.label}(${vp.width}x${vp.height})`;

      // R2 文書全体の横スクロール (どこか 1 つでも溢れると読み手には全体の問題として届く)
      if (r.docScrollWidth - r.winWidth > 2) {
        report('R2', vpName, `文書全体が横へ ${Math.round(r.docScrollWidth - r.winWidth)}px 溢れている`
          + ' (横スクロールは読み物として破綻)');
      }

      for (const sec of r.sections) {
        const where = `${vpName} §${sec.index}「${sec.title}」`;
        const content = [...sec.heads, ...sec.bodies, ...sec.figs];

        // R1 重なり
        for (let a = 0; a < content.length; a++) {
          for (let b = a + 1; b < content.length; b++) {
            const area = overlapArea(content[a], content[b], OVERLAP_TOLERANCE);
            if (area) {
              report('R1', where, `${content[a].role}${content[a].text ? `「${content[a].text}」` : ''} と `
                + `${content[b].role}${content[b].text ? `「${content[b].text}」` : ''} が ${area}px² 重なっている`);
            }
          }
        }

        // R2 コンテナからの横はみ出し
        for (const c of content) {
          const dx = Math.round(Math.max(0, c.right - r.container.right, r.container.left - c.left));
          if (dx > 2) {
            report('R2', where, `${c.role}${c.text ? `「${c.text}」` : ''} が本文幅の外へ 横 ${dx}px はみ出している`);
          }
        }

        // R3 行長 (本文として測る幅を持つものだけ)
        for (const b of sec.bodies) {
          if (b.width < r.container.width * BODY_WIDTH_RATIO) continue;
          // 全角 1 文字 ≒ font-size なので width/font-size がそのまま全角換算の行長になる
          const cpl = Math.round(b.width / b.fontSize);
          if (cpl > CPL_MAX) {
            report('R3', where, `本文「${b.text}」の 1 行が全角 ${cpl} 字ある `
              + `(目標 ${CPL_TARGET} 字・上限 ${CPL_MAX} 字。超えると次行の頭を見失う)。`
              + '本文幅 (--report-measure) か font-size で詰める');
          } else if (cpl < CPL_MIN) {
            report('R3', where, `本文「${b.text}」の 1 行が全角 ${cpl} 字しかない `
              + `(${CPL_MIN} 字未満は改行が多すぎて読み進めにくい)`);
          }
        }

        // R4 図解の幅 (モバイル幅では縮むのが正しいので見ない)
        if (vp.width >= NARROW_VIEWPORT) {
          for (const f of sec.figs) {
            const ratio = f.width / r.container.width;
            if (ratio < MIN_FIGURE_WIDTH_RATIO) {
              report('R4', where, `図解が本文幅の ${(ratio * 100).toFixed(0)}% しかない `
                + `(${(MIN_FIGURE_WIDTH_RATIO * 100).toFixed(0)}% 未満だと図中の文字が本文より小さく見え、読み飛ばされる)`);
            }
          }
        }

        // R6 切れ
        for (const c of sec.clipped) {
          report('R6', where, `<${c.tag}${c.cls ? ` class="${c.cls}"` : ''}> の内容が overflow:hidden で `
            + `${c.over}px 切れている`);
        }
      }

      // R5 見出しの近接 (節をまたぐので節ループの外で見る)
      for (const p of r.proximity) {
        if (p.gapAbove <= p.gapBelow) {
          report('R5', vpName, `見出し「${p.text}」の上の余白 ${p.gapAbove}px が下の余白 ${p.gapBelow}px 以下。`
            + '見出しは後続の内容に近づけないと、どちらに属するか読み違える');
        }
      }
      // R7 追従ナビ (screen のみ。print には浮遊 UI が無いのが正しい)
      // 実際にスクロールしてから測る。sticky は computed style が 'sticky' でも
      // 祖先に overflow:hidden があれば効かないので、宣言でなく結果を見る。
      if (vp.media !== 'print') {
        const nav = await page.evaluate(async () => {
          const wait = () => new Promise((res) => setTimeout(res, 250));
          const pick = () => ({
            topbar: document.querySelector('.report-topbar'),
            toc: document.querySelector('.report-toc--sidebar'),
          });
          const before = pick();
          const has = { topbar: !!before.topbar, toc: !!before.toc };
          // 生成器は節が 2 つ以上あるときだけ目次を出す (1 節の文書に目次は要らない)。
          // 検査もその条件を共有しないと、正しい単一節文書で必ず warning が出る。
          const sectionCount = document.querySelectorAll('.report-section[id]').length;
          // 文書の中ほどまで送る。末尾だと sticky 要素が親の終端で押し上げられる
          // 正常な挙動と、効いていない状態が区別できない。
          window.scrollTo(0, Math.max(0, (document.documentElement.scrollHeight - window.innerHeight) * 0.5));
          await wait();
          const after = pick();
          const seen = (el) => {
            if (!el) return null;
            const b = el.getBoundingClientRect();
            return {
              top: Math.round(b.top),
              bottom: Math.round(b.bottom),
              // 画面内に見えている高さ。0 なら追従していない
              visible: Math.round(Math.min(b.bottom, window.innerHeight) - Math.max(b.top, 0)),
            };
          };
          // R8: 追従 UI が本文を覆っていないか。R1 は scroll=0 の一回測定なので、
          // スクロールして初めて本文の上へ来る sticky 要素はどのペアにも入らない。
          const navEls = [after.topbar, after.toc].filter(Boolean);
          let covered = 0;
          let coveredSample = '';
          const texts = Array.prototype.slice.call(
            document.querySelectorAll('.report-section p, .report-section li'));
          for (const t of texts) {
            const tb = t.getBoundingClientRect();
            if (tb.bottom <= 0 || tb.top >= window.innerHeight || tb.width <= 0) continue;
            for (const nel of navEls) {
              const nb = nel.getBoundingClientRect();
              const ox = Math.min(tb.right, nb.right) - Math.max(tb.left, nb.left);
              const oy = Math.min(tb.bottom, nb.bottom) - Math.max(tb.top, nb.top);
              if (ox > 1 && oy > 1) {
                covered += 1;
                if (!coveredSample) coveredSample = (t.textContent || '').trim().slice(0, 24);
              }
            }
          }
          // 追従 UI が画面のどれだけを占めるか。見えていることだけを報酬にすると
          // 占有を増やす方向にしか圧力がかからないので、上限も同時に見る。
          const occupied = navEls.reduce((sum, el) => {
            const b = el.getBoundingClientRect();
            return sum + Math.max(0, Math.min(b.bottom, window.innerHeight) - Math.max(b.top, 0))
              * (b.width >= window.innerWidth * 0.5 ? 1 : 0);
          }, 0);
          return {
            has, sectionCount, covered, coveredSample,
            occupancy: Math.round((occupied / window.innerHeight) * 100),
            topbar: seen(after.topbar), toc: seen(after.toc), winH: window.innerHeight,
          };
        });
        if (!nav.has.topbar) {
          report('R7', vpName, '追従ヘッダー (.report-topbar) が無い。'
            + 'スクロール後に文書名と現在位置の手掛かりが消える');
        } else if (nav.topbar.visible <= 0) {
          report('R7', vpName, `追従ヘッダーがスクロール後に画面外へ出ている (top=${nav.topbar.top}px)。`
            + 'sticky が祖先の overflow に潰されていないか確認する');
        }
        if (!nav.has.toc) {
          if (nav.sectionCount >= 2) {
            report('R7', vpName, `目次 (.report-toc--sidebar) が無い。節が ${nav.sectionCount} つあるのに`
              + '任意の節へ飛ぶ手段が読者に無い');
          }
        } else if (nav.toc.visible <= 0) {
          report('R7', vpName, `目次がスクロール後に画面外へ出ている (top=${nav.toc.top}px)。`
            + '常時追従していないと、読み進めた先から他の節へ移動できない');
        }
        if (nav.covered > 0) {
          report('R8', vpName, `追従 UI がスクロール後に本文 ${nav.covered} 要素を覆っている`
            + `(例:「${nav.coveredSample}」)。読んでいる最中の行が隠れる`);
        }
        if (nav.occupancy > NAV_OCCUPANCY_MAX) {
          report('R8', vpName, `追従 UI が画面の縦 ${nav.occupancy}% を占める`
            + ` (上限 ${NAV_OCCUPANCY_MAX}%)。到達性のための UI が本文の面積を奪っている`);
        }
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }

  const failed = errors > 0 || (strict && warnings > 0);
  console.log(`report layout contract: viewports=${viewports.length} errors=${errors} `
    + `warnings=${warnings} -> ${failed ? 'FAIL' : 'PASS'}`);
  process.exit(failed ? 1 : 0);
}

run().catch((err) => {
  console.error(`ERROR [R0] ${err && err.message ? err.message : err}`);
  process.exit(1);
});
