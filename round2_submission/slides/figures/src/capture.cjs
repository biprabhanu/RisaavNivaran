// Fresh 1920x1080 screenshots of the live app for the slides.
// Run from repo root: node round2_submission/slides/figures/src/capture.cjs [baseURL]
const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../../../../frontend/node_modules/playwright'));
const BASE = process.argv[2] || 'http://localhost:8000';
const OUT = path.resolve(__dirname, '..');
const shots = { 3: 'replay-plan', 5: 'replay-ogi-unavailable', 6: 'replay-bayes-update', 8: 'replay-rejected', 9: 'replay-verified', 11: 'replay-reopened' };
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const snap = async (name) => { await page.waitForTimeout(1500); await page.screenshot({ path: path.join(OUT, name + '.png') }); console.log('saved', name); };
  const step = async () => { const t = await page.getByTestId('step-counter').innerText(); const m = /Step (\d+)/.exec(t); return m ? +m[1] : -1; };
  await page.goto(BASE + '/#/');
  await page.getByTestId('llm-badge').waitFor();
  await page.getByTestId('reset-demo').click();
  await page.getByTestId('toast').waitFor();
  await page.getByTestId('toast').waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  await snap('landing');
  await page.getByTestId('start-demo').click();
  await page.waitForFunction(() => /Step 0/.test(document.querySelector('[data-testid=step-counter]')?.textContent || ''));
  for (let i = 0; i < 25; i++) {
    if (await page.getByTestId('replay-done').isVisible()) break;
    const approve = page.getByTestId('approve-button');
    const done = page.waitForResponse((r) => r.url().includes('/api/replay/step'));
    if (await approve.isVisible()) await approve.click(); else await page.getByTestId('replay-next').click();
    await done;
    await page.waitForFunction(() => document.querySelector('[data-testid=replay-next]')?.getAttribute('data-busy') === 'false');
    const s = await step();
    console.log('step', s);
    if (shots[s]) { await snap(shots[s]); delete shots[s]; }
  }
  for (const [route, name] of [['/#/planner', 'planner'], ['/#/audit', 'audit'], ['/#/evaluation', 'evaluation'], ['/#/cases/KJ-2025-02', 'case'], ['/#/map', 'map'], ['/#/verification', 'verification'], ['/#/approvals', 'approvals'], ['/#/whatif', 'whatif']]) {
    await page.goto(BASE + route); await page.waitForLoadState('networkidle'); await snap(name);
  }
  // Leave a clean demo state for the presenters.
  await page.goto(BASE + '/#/');
  await page.getByTestId('reset-demo').click();
  await page.getByTestId('toast').waitFor();
  console.log('reset done; missing shots:', Object.values(shots));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
