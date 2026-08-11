/**
 * Playwright runtime path contract for slide-report-generator.
 *
 * Browser binaries are platform-specific and therefore restored at install
 * time under vendor/playwright-browsers instead of relying on a user-global
 * Playwright cache.
 */
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const scriptsDir = dirname(fileURLToPath(import.meta.url));

export const vendorDir = resolve(scriptsDir, '..');
export const pluginRoot = resolve(vendorDir, '..');
export const pluginLocalBrowsersPath = resolve(vendorDir, 'playwright-browsers');

export function configurePluginLocalPlaywright() {
  process.env.PLAYWRIGHT_BROWSERS_PATH = pluginLocalBrowsersPath;
  return pluginLocalBrowsersPath;
}

export function setupCommand() {
  return `python3 "${resolve(pluginRoot, 'scripts', 'setup-playwright.py')}" --install`;
}
