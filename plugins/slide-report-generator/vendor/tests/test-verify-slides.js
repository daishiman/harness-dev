#!/usr/bin/env node
/**
 * Acceptance test for the Node/plugin-local verify-slides path.
 */
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { spawnSync } from 'child_process';
import { fileURLToPath } from 'url';

const root = mkdtempSync(join(tmpdir(), 'verify-slides-test-'));
try {
  const html = join(root, 'index.html');
  const shots = join(root, 'screenshots');
  writeFileSync(
    html,
    '<!doctype html><style>html,body{margin:0}.slide-area{width:1600px;height:900px}.slider__item{display:none;width:100%;height:100%}.slider__item.is-active{display:block}</style><main class="slide-area"><section class="slider__item is-active">One</section><section class="slider__item">Two</section></main>',
  );
  const script = fileURLToPath(new URL('../scripts/verify-slides.js', import.meta.url));
  const ratio = spawnSync(process.execPath, [script, html, '--check-ratio'], {
    encoding: 'utf8',
  });
  if (ratio.status !== 0) throw new Error(ratio.stderr || ratio.stdout);
  const capture = spawnSync(process.execPath, [script, html, shots], {
    encoding: 'utf8',
  });
  if (capture.status !== 0) throw new Error(capture.stderr || capture.stdout);
  for (const file of ['slide_01.png', 'slide_02.png']) {
    if (!existsSync(join(shots, file))) throw new Error(`screenshot missing: ${file}`);
  }
  console.log('test-verify-slides: PASS');
} finally {
  rmSync(root, { recursive: true, force: true });
}
