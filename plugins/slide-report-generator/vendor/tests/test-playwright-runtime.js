#!/usr/bin/env node
/**
 * Plugin-local Playwright path and Chromium acceptance test.
 */
import { existsSync } from 'fs';
import {
  configurePluginLocalPlaywright,
  pluginLocalBrowsersPath,
} from '../scripts/playwright-runtime.js';

const configured = configurePluginLocalPlaywright();
if (configured !== pluginLocalBrowsersPath) {
  throw new Error(`configured browser path mismatch: ${configured}`);
}
if (process.env.PLAYWRIGHT_BROWSERS_PATH !== pluginLocalBrowsersPath) {
  throw new Error('PLAYWRIGHT_BROWSERS_PATH is not plugin-local');
}

const { chromium } = await import('playwright');
const executable = chromium.executablePath();
if (!executable.startsWith(pluginLocalBrowsersPath) || !existsSync(executable)) {
  throw new Error(`plugin-local Chromium is unavailable: ${executable}`);
}

console.log(`test-playwright-runtime: PASS (${executable})`);
