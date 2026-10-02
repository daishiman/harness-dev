#!/usr/bin/env node

import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { check, finish, skillRoot } from './_harness.mjs'

const referenceDir = join(skillRoot, 'assets/reference')
const htmlNames = ['catalog.html', 'index.html', 'pop.html']
const html = Object.fromEntries(await Promise.all(htmlNames.map(async (name) => [name, await readFile(join(referenceDir, name), 'utf8')])))
const styles = await readFile(join(referenceDir, 'styles.css'), 'utf8')
const appJs = await readFile(join(referenceDir, 'app.js'), 'utf8')
const interactions = await readFile(join(referenceDir, 'reference-interactions.js'), 'utf8')
const referenceReadme = await readFile(join(referenceDir, 'README.md'), 'utf8')
const standardCss = await readFile(join(referenceDir, '../standard/standard-color-system.css'), 'utf8')
const catalogProfile = JSON.parse(await readFile(join(referenceDir, 'catalog-default-profile.json'), 'utf8'))

function visibleText(source) {
  return source
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<style\b[\s\S]*?<\/style>/gi, ' ')
    .replace(/<script\b[\s\S]*?<\/script>/gi, ' ')
    .replace(/<svg\b[\s\S]*?<\/svg>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, ' ')
    .trim()
}

function classNames(source) {
  return [...source.matchAll(/\bclass\s*=\s*["']([^"']+)["']/gi)].flatMap((match) => match[1].split(/\s+/))
}

const bannedClasses = ['page-lede', 'hint', 'spec-note', 'footnote', 'hand-note', 'f-sub', 'pop-footer', 'kbd-hint']
for (const [name, source] of Object.entries(html)) {
  const classes = new Set(classNames(source))
  for (const className of bannedClasses) {
    check(!classes.has(className), `${name}: .${className} is absent from DOM`)
  }
}

const bannedVisiblePatterns = [
  ['skill name', /jp-web-design|ux-design/i],
  ['model/debug note', /モデルケース|デバッグ|debug/i],
  ['implementation terminology', /\bCSS\b|grid-cols|color-mix|placeholderをラベル代わり|実装理由|操作規則/i],
  ['interaction implementation labels', /hover|pressed|\benter\b|Enterキー/i],
  ['CSS measurements or tokens', /\b\d+(?:\.\d+)?px\b|--[a-z][a-z0-9-]*/i]
]

for (const [name, source] of Object.entries(html)) {
  const text = visibleText(source)
  for (const [label, pattern] of bannedVisiblePatterns) {
    check(!pattern.test(text), `${name}: visible ${label} is absent`)
  }
}

const catalog = html['catalog.html']
check(!/\bclass\s*=\s*["'][^"']*\bspec-note\b/i.test(catalog), 'catalog.html: spec-note count is zero')
check(!/<code\b/i.test(catalog.replace(/<style\b[\s\S]*?<\/style>/gi, '')), 'catalog.html: visible code elements are absent')

const headings = [...catalog.matchAll(/<h[1-6]\b[^>]*>([\s\S]*?)<\/h[1-6]>/gi)].map((match) => visibleText(match[1]))
for (const heading of ['部品カタログ', '標準カラー', 'サイドナビ', 'ボタン', '動き', '状態', '入力', '選択', '一覧', '案内', '用語', '比較', '文字と数字']) {
  check(headings.includes(heading), `catalog.html: short heading '${heading}' exists`)
}
check(headings.every((heading) => !/[（(—+\/]/.test(heading)), 'catalog.html: headings contain no implementation annotations')

for (const className of bannedClasses) {
  const selector = new RegExp(`\\.${className.replaceAll('-', '\\-')}(?![a-z0-9_-])`, 'i')
  check(!selector.test(styles) && !selector.test(html['pop.html']), `reference styles: unused .${className} definition is absent`)
}

check(!/fonts\.googleapis\.com|fonts\.gstatic\.com/i.test(Object.values(html).join('\n')), 'reference HTML: external Google Fonts dependency is absent')
check(!/['"`]要確認キュー|['"`]キューを見る/.test(appJs), 'app.js: internal queue wording is not inserted into UI')

check(/--font-ui:\s*-apple-system,\s*BlinkMacSystemFont/.test(styles), 'styles.css: system-first UI font token')
check(/--font-display:\s*"SF Pro Display",\s*-apple-system/.test(styles), 'styles.css: display font token has system fallback')
for (const [token, value] of [
  ['body', '16px'],
  ['control', '16px'],
  ['label', '16px'],
  ['section', '18px'],
  ['page', 'clamp\\(22px, 2vw, 24px\\)'],
  ['app', '20px'],
  ['display', 'clamp\\(40px, 7vw, 56px\\)']
]) {
  check(new RegExp(`--font-size-${token}:\\s*${value};`).test(styles), `styles.css: ${token} size token is readable`)
}
check(/body\s*\{[\s\S]*?font-size:\s*var\(--font-size-body\)/.test(styles), 'styles.css: body text uses 16px token')
check(/\.btn\s*\{[\s\S]*?font-size:\s*var\(--font-size-control\)/.test(styles), 'styles.css: buttons use 16px control token')
check(/\.app-nav button\s*\{[\s\S]*?font-size:\s*var\(--font-size-control\)/.test(styles), 'styles.css: navigation uses 16px control token')
check(/table\s*\{[^}]*font-size:\s*var\(--font-size-body\)/.test(styles), 'styles.css: tables use body text token')
check(/--tap:\s*44px;/.test(styles), 'styles.css: tap target token is 44px')
check(/@media \(max-width: 767px\)\s*\{\s*\.field :where\(input, select, textarea\)\s*\{\s*font-size:\s*16px;\s*\}/.test(styles), 'styles.css: mobile inputs are at least 16px')
check(/html\s*\{[^}]*overflow-x:\s*clip/.test(styles) && /body\s*\{[^}]*overflow-x:\s*clip/.test(styles), 'styles.css: page-level horizontal overflow is clipped')
check(/@media \(max-width: 639px\)[\s\S]*?padding-right:\s*max\(16px, env\(safe-area-inset-right\)\)[\s\S]*?padding-left:\s*max\(16px, env\(safe-area-inset-left\)\)/.test(styles), 'styles.css: mobile main uses 16px safe-area inset')
check(/\.app-shell \.side-nav\s*\{\s*display:\s*none;\s*\}[\s\S]*?body > \.bottom-tabs\s*\{\s*display:\s*grid;\s*\}/.test(styles), 'styles.css: mobile app shell changes sidebar to bottom tabs')
check(/<div class="app-shell">[\s\S]*?<nav class="side-nav"[\s\S]*?<nav class="bottom-tabs"/.test(html['index.html']), 'index.html: desktop sidebar and mobile bottom tabs share the app navigation')
check(/\.catalog-grid,[\s\S]*?\.def-list\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\);\s*\}/.test(styles), 'styles.css: mobile content grids become one column')
check(/\.swatch-row,[\s\S]*?\.pop-chips\s*\{\s*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\);\s*\}/.test(styles), 'styles.css: compact semantic grids use safe two-column tracks')
check(/\.catalog-section tbody td::before\s*\{[\s\S]*?content:\s*attr\(data-label\)/.test(styles), 'styles.css: mobile table rows expose label-value pairs')
check([...catalog.matchAll(/<tbody>[\s\S]*?<\/tbody>/gi)].every((body) => !/<td\b(?![^>]*\bdata-label=)/i.test(body[0])), 'catalog.html: table cells provide mobile data labels')
check(/\.field-pair\s*\{\s*align-items:\s*start;\s*\}/.test(styles) && /@media \(min-width: 641px\)[\s\S]*?\.field-pair\s*\{\s*grid-template-rows:\s*auto var\(--tap\) minmax\(1\.7em, auto\);\s*\}[\s\S]*?grid-template-rows:\s*subgrid;/.test(styles), 'styles.css: desktop field pair shares label, control, and validation rows')
check(!/@media \(max-width: 640px\)[\s\S]{0,180}\.field-pair > \.field/.test(styles), 'styles.css: mobile field rows use content height without a reserved empty validation row')
check(/id="cat-email-err"[^>]*aria-invalid="true"[^>]*aria-describedby="cat-email-error"/.test(catalog) && /class="error-msg" id="cat-email-error"/.test(catalog), 'catalog.html: invalid input is programmatically linked to its recovery message')

const navigationGlass = styles.match(/:is\(\.side-nav, \.bottom-tabs\)\s*\{([\s\S]*?)\n\}/)?.[1] ?? ''
check(navigationGlass.length > 0, 'styles.css: sidebar and bottom tabs share one material block')
check(/navigation-glass-fill[\s\S]*?glass-specular-rim[\s\S]*?backdrop-filter:\s*var\(--glass-filter\)[\s\S]*?border:\s*1px solid transparent[\s\S]*?navigation-glass-shadow/.test(navigationGlass), 'styles.css: shared navigation uses layered soft Liquid Glass optics')
check(!/action-primary-bg|status-info-text|brand-accent/.test(navigationGlass), 'styles.css: shared navigation material excludes CTA, status, and accent colors')
check(/--navigation-glass-fill:[\s\S]*?var\(--nav-hover\)[\s\S]*?var\(--nav-background\)/.test(styles), 'styles.css: shared navigation material is derived from canonical nav roles')
check(/:is\(\.side-nav, \.bottom-tabs\) :where\(a, button\)\s*\{[\s\S]*?min-height:\s*var\(--tap\)[\s\S]*?color:\s*var\(--nav-text-muted\)[\s\S]*?font-size:\s*var\(--font-size-control\)/.test(styles), 'styles.css: both navigation variants share 44px and 16px item rules')
check(!/background-color:\s*var\(--nav-background\)/.test(styles), 'styles.css: legacy solid indigo navigation plane is absent')
check(/--nav-background:\s*var\(--p-surface-subtle\);[\s\S]*?--nav-text:\s*var\(--p-ink\);[\s\S]*?--nav-text-muted:\s*var\(--p-ink-secondary\);[\s\S]*?--nav-hover:\s*var\(--p-brand-indigo-soft\);[\s\S]*?--nav-selected-indicator:\s*var\(--p-brand-indigo\);/.test(standardCss), 'standard-color-system.css: navigation roles are light with indigo limited to selection')
check(/@media \(prefers-reduced-transparency: reduce\), \(prefers-contrast: more\)[\s\S]*?:is\(\.side-nav, \.bottom-tabs\)\s*\{[^}]*background:\s*var\(--surface-alt\);[^}]*backdrop-filter:\s*none;/.test(styles), 'styles.css: both navigation variants share an opaque accessibility fallback')

const card = styles.match(/\.card\s*\{([\s\S]*?)\n\}/)?.[1] ?? ''
check(!/backdrop-filter|var\(--glass-fill/.test(card), 'styles.css: content cards use standard material')
check(/\.app-header\s*\{[\s\S]*?var\(--glass-fill\)/.test(styles), 'styles.css: floating header retains Liquid Glass')
check(/\.modal\s*\{[\s\S]*?var\(--glass-fill-strong\)/.test(styles), 'styles.css: modal retains Liquid Glass')
check(/--glass-specular-rim:\s*linear-gradient\(135deg,[\s\S]*?transparent 64%/.test(styles), 'styles.css: normal glass rim uses an asymmetric low-contrast specular gradient')
check(/--glass-specular-rim-hover:[\s\S]*?--glass-specular-rim-pressed:/.test(styles), 'styles.css: hover raises and pressed lowers the optical rim')
check(/\.app-header\s*\{[\s\S]*?var\(--glass-fill\) padding-box, var\(--glass-specular-rim\) border-box;[\s\S]*?border:\s*1px solid transparent;/.test(styles), 'styles.css: functional glass uses transparent border with layered padding-box/border-box optics')
check(/\.btn-secondary\s*\{[\s\S]*?var\(--glass-fill-strong\) padding-box, var\(--glass-specular-rim\) border-box;[\s\S]*?border:\s*1px solid transparent;/.test(styles), 'styles.css: regular text controls avoid a uniform solid outline')
check(/\.field :where\(input\[type="text"\], input\[type="email"\], select, textarea\)\s*\{[\s\S]*?border:\s*1px solid var\(--input-border\);[\s\S]*?background:\s*color-mix\(in srgb, var\(--input-bg\) 96%, var\(--surface-alt\)\);[\s\S]*?box-shadow:\s*inset/.test(styles), 'styles.css: content inputs have a continuous control border, surface fill, and inset depth')
check(/\.field :where\(input, select, textarea\):hover\s*\{[^}]*border-color:\s*var\(--input-border-hover\)/.test(styles) && /\.field :where\(input, select, textarea\):focus\s*\{\s*border-color:\s*var\(--input-border-focus\)/.test(styles), 'styles.css: content input hover and focus strengthen the semantic border')
check(/\.field :where\(input, select, textarea\):disabled\s*\{[^}]*border-color:\s*var\(--action-disabled-border\)[^}]*background:\s*var\(--action-disabled-bg\)/.test(styles), 'styles.css: disabled content controls remain identifiable')
check(/\[aria-current="page"\][\s\S]*?nav-selected-indicator/.test(styles) && /\[aria-invalid="true"\]\s*\{\s*border-color:\s*var\(--input-invalid-border\)/.test(styles), 'styles.css: selected and invalid states retain clear semantic indicators')
check(/\.pop-header\s*\{[\s\S]*?var\(--glass-fill-strong\) padding-box, var\(--glass-specular-rim\) border-box;/.test(html['pop.html']) && /\.pop-cta\s*\{[\s\S]*?var\(--glass-specular-rim\)/.test(html['pop.html']), 'pop.html: header and primary action use the shared optical glass structure')
check(/@media \(prefers-reduced-transparency: reduce\), \(prefers-contrast: more\)[\s\S]*?\.pop-header,[\s\S]*?backdrop-filter:\s*none/.test(html['pop.html']), 'pop.html: optical glass has reduced-transparency and contrast fallback')
check(/--motion-instant:\s*90ms;[\s\S]*--motion-fast:\s*140ms;/.test(styles), 'styles.css: hover timing stays within 90–140ms')
check(/\.pressable:active\s*\{\s*transform:\s*scale\(0\.985\);\s*\}/.test(styles), 'styles.css: pressed scale is .985')
check(/@media \(prefers-reduced-motion: reduce\)/.test(styles), 'styles.css: reduced-motion fallback exists')
check(/@media \(prefers-reduced-transparency: reduce\), \(prefers-contrast: more\)/.test(styles), 'styles.css: transparency and contrast fallback exists')
check(/function bindExclusive/.test(interactions) && /event\.key === 'Enter' \|\| event\.key === ' '/.test(interactions) && /ArrowRight/.test(interactions) && /aria-pressed/.test(interactions), 'reference-interactions.js: exclusive controls share click, keyboard, and ARIA state logic')
check(/function bindTabs/.test(interactions) && /data-tab-panel/.test(interactions) && /aria-current/.test(interactions), 'reference-interactions.js: navigation shares current-item and panel switching logic')
check(/data-action-message[\s\S]*?data-clear-form[\s\S]*?data-filter-table[\s\S]*?data-sort-table/.test(interactions), 'reference-interactions.js: actions, form clear, filtering, and sorting share one event layer')
check(/inline-reference-interactions:start[\s\S]*?global\.ReferenceUI/.test(catalog), 'catalog.html: shared interaction helper is generated inline for standalone use')
check(/id="catalog-nav" data-tabs[\s\S]*?data-tab-panel[\s\S]*?data-clear-form[\s\S]*?data-exclusive[\s\S]*?data-filter-table[\s\S]*?data-sort-table[\s\S]*?<details/.test(catalog), 'catalog.html: visible navigation, selection, form, table, and disclosure examples are operable')
check(/id="pop-send"/.test(html['pop.html']) && /<script src="reference-interactions\.js"><\/script>/.test(html['pop.html']) && /btn-reply-unanswered/.test(html['index.html']) && /btn-reply-unanswered/.test(appJs), 'reference pages: Pop and app actions are connected to a visible result')
check(!/\bhint\b|\.hand-note|\.switch\b/.test(referenceReadme), 'reference README: removed helper-copy and orphan switch migration instructions')
check(!/\.switch(?:\s|\{|:|\[)/.test(html['pop.html']) && !/トグル/.test(html['pop.html']), 'pop.html: orphan switch selectors and toggle comments are absent')

// 専門用語の段階開示。説明文が常時表示に戻る・印から説明へ辿れない・同じ文が2か所に増える、を防ぐ。
check(/\.term\s*\{[\s\S]*?border-bottom:\s*1px dashed/.test(styles), 'styles.css: term mark is a dotted underline on body text')
check(/\.term-q\s*\{[\s\S]*?border-radius:\s*999px/.test(styles), 'styles.css: term mark carries a round question badge')
check(/\.tooltip\.tip-rich\s*\{[\s\S]*?position:\s*fixed/.test(styles) && /\.tooltip\.tip-rich\[hidden\]\s*\{\s*display:\s*none;\s*\}/.test(styles), 'styles.css: term explanation floats and stays hidden until asked for')
check(/details\.howto\s*\{/.test(styles) && /\.glossary\s*\{/.test(styles), 'styles.css: chart how-to and glossary have their own collapsed blocks')

const terms = [...catalog.matchAll(/<a class="term" href="#([^"]+)" data-term="([^"]+)">([\s\S]*?)<\/a>/g)]
check(terms.length >= 2, 'catalog.html: term marks demonstrate the pattern')
check(terms.every(([, , , inner]) => /<span class="term-q" aria-hidden="true">\?<\/span>/.test(inner)), 'catalog.html: every term mark carries a question badge that is not read aloud')
const definitions = new Map([...catalog.matchAll(/<dt id="([^"]+)">([\s\S]*?)<\/dt>\s*<dd>([\s\S]*?)<\/dd>/g)].map((match) => [match[1], { label: visibleText(match[2]), body: match[3] }]))
check(terms.every(([, id]) => definitions.has(id)), 'catalog.html: every term mark resolves to a glossary entry')
check(terms.every(([, id, label]) => definitions.get(id)?.label === label), 'catalog.html: term mark and glossary entry name the same term')
check([...definitions.values()].every(({ body }) => /<span class="gl-what">/.test(body) && /<span class="gl-how">/.test(body)), 'catalog.html: each glossary entry states what it is and how to read it')
check(/<aside class="glossary[^"]*">\s*<details>\s*<summary>/.test(catalog), 'catalog.html: the glossary stays collapsed until opened')
check(/<details class="howto">\s*<summary>/.test(catalog) && !/<details class="howto" open/.test(catalog), 'catalog.html: the chart how-to stays collapsed until opened')
const explanations = [...definitions.values()].map(({ body }) => visibleText(body.match(/<span class="gl-what">([\s\S]*?)<\/span>/)?.[1] ?? ''))
check(explanations.every((sentence) => sentence && catalog.split(sentence).length === 2), 'catalog.html: each explanation sentence is written in exactly one place')
check(/function bindTerms/.test(interactions) && /getElementById\(decodeURIComponent/.test(interactions), 'reference-interactions.js: the floating explanation is read from the glossary instead of duplicated')
check(/event\.preventDefault\(\)[\s\S]{0,200}pinned = term/.test(interactions), 'reference-interactions.js: pressing a term pins its explanation instead of jumping away')
check(/restoringFocus = true\s*\n\s*term\.focus\(\)/.test(interactions), 'reference-interactions.js: closing with Escape returns focus without reopening the explanation')

// catalog-default verify の検査語が参照画面・部品CSSと食い違うと、検査が空振りしても気づけない。
const referenceSources = [...Object.values(html), appJs].join('\n')
for (const denied of catalogProfile.consumer_source_denylist) {
  check(referenceSources.includes(denied), `catalog-default-profile: denylist entry '${denied}' exists in reference sample screens`)
}
for (const [component, marker] of Object.entries(catalogProfile.component_markers)) {
  const selector = new RegExp(`\\.${marker.replaceAll('-', '\\-')}(?![a-z0-9_-])`, 'i')
  check(selector.test(styles), `catalog-default-profile: ${component} marker .${marker} is defined in styles.css`)
}

finish()
