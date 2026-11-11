/** Check the generated course as a static site, including script-free navigation. */
import { chromium, expect } from '@playwright/test';
import { createServer } from 'node:http';
import { readFile, readdir, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname, relative, join } from 'node:path';

const root = resolve(import.meta.dirname, '../../..');
const output = resolve(process.argv[2] || join(root, 'temp/TEMP_tutorial_refresh/html-browser'));
const parts = relative(root, output).split('/');
if (parts[0] !== 'temp' || !parts[1]?.startsWith('TEMP_')) throw new Error('Use repository temp/TEMP_ output.');
await mkdir(output, { recursive: true });
const scratch = join(output, 'scratch');
await mkdir(scratch, { recursive: true });
Object.assign(process.env, { TMPDIR: scratch, TMP: scratch, TEMP: scratch });
const types: Record<string, string> = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.jpg': 'image/jpeg', '.json': 'application/json', '.md': 'text/plain' };
const server = createServer(async (request, response) => {
  const name = resolve(root, '.' + decodeURIComponent(new URL(request.url!, 'http://localhost').pathname));
  if (relative(root, name).startsWith('..')) { response.writeHead(403).end(); return; }
  try { response.setHeader('Content-Type', types[extname(name)] || 'application/octet-stream'); response.end(await readFile(name)); }
  catch { response.writeHead(404).end(); }
});
await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${(server.address() as { port: number }).port}/docs/tutorials/`;
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const results: object[] = [];
try {
  const files = (await readdir(join(root, 'docs/tutorials'))).filter(name => name.endsWith('.html'));
  for (const width of [1440, 1280, 1024, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    for (const file of files) {
      await page.goto(base + file);
      await page.locator('img').evaluateAll(images => images.forEach(image => image.setAttribute('loading', 'eager')));
      await expect.poll(() => page.locator('img').evaluateAll(images => images.every(image => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0))).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await expect(page.locator('h1')).toHaveCount(1);
      if (width === 390) {
        const lessons = page.getByRole('button', { name: 'Lessons', exact: true });
        await lessons.focus(); await page.keyboard.press('Enter');
        await expect(lessons).toHaveAttribute('aria-expanded', 'true');
        await expect(page.locator('#sidebar')).toBeVisible();
        await page.keyboard.press('Escape');
        await expect(lessons).toBeFocused();
        await expect(lessons).toHaveAttribute('aria-expanded', 'false');
      }
      if (['index.html', '02-component-ports.html', 'diagnostics.html', 'catalog-reuse.html'].includes(file))
        await page.screenshot({ path: join(output, `${width}-${file}.png`), fullPage: true });
      results.push({ file, width, status: 'passed', images: await page.locator('img').count() });
    }
    await context.close();
  }
  const plain = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 900 } });
  const page = await plain.newPage();
  await page.goto(base + 'index.html');
  await expect(page.locator('#sidebar')).toBeVisible();
  await page.locator('#sidebar a[href="02-component-ports.html"]').click();
  await expect(page).toHaveURL(/02-component-ports.html$/);
  await expect(page.locator('#actions')).toBeVisible();
  results.push({ scenario: 'script-free mobile navigation', status: 'passed' });
  await plain.close();
} finally {
  await writeFile(join(output, 'results.json'), JSON.stringify(results, null, 2) + '\n');
  await browser.close();
  await new Promise<void>(done => server.close(() => done()));
}
console.log(`Passed ${results.length} static course checks.`);
