// Records the 60-second product video (silent, captioned) by driving the real app with Playwright.
// Run from frontend/ so Playwright resolves:  cd frontend && node ../round2_submission/slides/figures/src/record_video.cjs [baseURL]
// Output: round2_submission/slides/video/raw.webm  (convert to MP4 with ffmpeg; see INFO.md / make_video.sh)
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const BASE = process.argv[2] || 'http://localhost:8000';
const OUT = path.resolve(__dirname, '../../video');

// One short caption per replay step (what the judges should notice).
const CAPTION = {
  1: 'A real Carbon Mapper plume over the Kanjur landfill opens a case',
  2: 'The agent keeps three competing sources: waste surface, gas collection, flare',
  3: 'It ranks checks by information per rupee and day: records request first',
  4: 'A human approves the investigation before anything is sent',
  5: 'Inspector unavailable: the action is excluded and the plan re-ranks',
  6: "Records show a gas-system fault: Bayes' rule moves gas collection to 65%",
  7: 'A human approves the source attribution',
  8: 'The operator claims a repair. No independent measurement: closure REJECTED',
  9: 'Independent measurement: 760 < 1,302 kg/h, so the reduction is verified',
  10: 'A human approves the final closure',
  11: 'April 2026: a real plume of ~3,300 kg/h returns. The case REOPENS',
};
const KEY = new Set([6, 8, 9, 11]); // dwell longer on the show-stopper moments

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } } });
  const page = await ctx.newPage();

  const caption = (text, sub = '') =>
    page.evaluate(([t, s]) => {
      let el = document.getElementById('pp-cap');
      if (!el) {
        el = document.createElement('div');
        el.id = 'pp-cap';
        el.style.cssText = 'position:fixed;left:50%;bottom:36px;transform:translateX(-50%);z-index:99999;max-width:1500px;' +
          'background:#ffffff;border:1px solid #e2e8f0;border-left:8px solid #0d9488;border-radius:14px;padding:18px 30px;' +
          'box-shadow:0 10px 30px rgba(15,23,42,.18);font:600 30px Inter,system-ui,sans-serif;color:#0f172a;text-align:left';
        document.body.appendChild(el);
      }
      el.innerHTML = t + (s ? `<div style="font:500 20px Inter,system-ui,sans-serif;color:#64748b;margin-top:6px">${s}</div>` : '');
    }, [text, sub]);

  const card = (html) =>
    page.evaluate((h) => {
      const el = document.createElement('div');
      el.style.cssText = 'position:fixed;inset:0;z-index:100000;background:#ffffff;display:flex;flex-direction:column;' +
        'align-items:center;justify-content:center;font-family:Inter,system-ui,sans-serif;color:#0f172a;text-align:center';
      el.innerHTML = h;
      document.body.appendChild(el);
      return true;
    }, html);

  // Clean state, then the landing page.
  await page.goto(`${BASE}/#/`);
  await page.waitForLoadState('networkidle');
  await page.getByTestId('reset-demo').click();
  await page.getByTestId('toast').waitFor();
  await caption('PlumeProof: from satellite methane alerts to verified mitigation', 'Only 13% of 5,000+ UN methane alerts get a response. Detection is solved; follow-through is not.');
  await page.waitForTimeout(4000);

  await page.getByTestId('start-demo').click();
  await page.getByTestId('step-counter').waitFor();
  await page.waitForTimeout(1200);
  const stepNo = async () => parseInt(((await page.getByTestId('step-counter').innerText()).match(/Step (\d+)/) || [])[1] ?? '-1', 10);

  for (let guard = 0; guard < 30; guard++) {
    if (await page.getByTestId('replay-done').isVisible()) break;
    const approve = page.getByTestId('approve-button');
    if (await approve.isVisible()) await approve.click();
    else await page.getByTestId('replay-next').click();
    await page.waitForSelector('[data-testid=replay-next][data-busy=false]');
    await page.waitForTimeout(300);
    const s = await stepNo();
    if (CAPTION[s]) await caption(CAPTION[s], s === 8 || s === 11 ? '' : `Step ${s} of 11 · real satellite data, simulated operations`);
    await page.waitForTimeout(KEY.has(s) ? 5200 : 3200);
  }

  await card(`<div style="font-weight:800;font-size:88px;letter-spacing:-1px">PlumeProof</div>
    <div style="font-size:34px;color:#475569;margin-top:10px">Every methane plume deserves an investigation.<br>Every claimed fix deserves evidence.</div>
    <div style="margin-top:44px;font-size:30px;font-weight:700;color:#0d9488">plumeproof.onrender.com</div>
    <div style="margin-top:8px;font-size:26px;color:#64748b">github.com/biprabhanu/RisaavNivaran · Team RisaavNivaran, IIT Bombay</div>`);
  await page.waitForTimeout(3500);

  const v = page.video();
  await ctx.close();
  const p = await v.path();
  fs.renameSync(p, path.join(OUT, 'raw.webm'));
  // Leave the live app clean for whoever uses it next.
  const b2 = await browser.newPage();
  await b2.goto(`${BASE}/#/`); await b2.getByTestId('reset-demo').click(); await b2.getByTestId('toast').waitFor();
  await browser.close();
  console.log('saved', path.join(OUT, 'raw.webm'));
})();
