#!/usr/bin/env node
/**
 * Restore the platform-appropriate Chromium build into the plugin-local cache.
 *
 * Called automatically by vendor/package.json postinstall and may also be run
 * directly after a Playwright package update.
 */
import { existsSync, mkdirSync } from 'fs';
import { resolve } from 'path';
import { spawnSync } from 'child_process';
import {
  configurePluginLocalPlaywright,
  pluginLocalBrowsersPath,
  vendorDir,
} from './playwright-runtime.js';

configurePluginLocalPlaywright();
mkdirSync(pluginLocalBrowsersPath, { recursive: true });

const playwrightCli = resolve(vendorDir, 'node_modules', 'playwright', 'cli.js');
if (!existsSync(playwrightCli)) {
  console.error(`playwright package missing: ${playwrightCli}`);
  console.error('Run npm ci in the plugin vendor directory first.');
  process.exit(2);
}

const result = spawnSync(
  process.execPath,
  [playwrightCli, 'install', 'chromium'],
  {
    cwd: vendorDir,
    env: process.env,
    stdio: 'inherit',
  },
);

if (result.error) {
  console.error(`Playwright Chromium install failed: ${result.error.message}`);
  process.exit(2);
}
if (result.status !== 0) process.exit(result.status ?? 2);

const { chromium } = await import('playwright');
const executable = chromium.executablePath();
if (!executable || !existsSync(executable)) {
  console.error(`Playwright Chromium executable missing after install: ${executable || '(empty)'}`);
  process.exit(2);
}

console.log(`Playwright Chromium ready: ${executable}`);
