import { expect, test, type Page } from '@playwright/test';

function trackConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && !/tile\.openstreetmap|Failed to load resource/i.test(msg.text())) errors.push(msg.text());
  });
  page.on('pageerror', (err) => errors.push(err.message));
  return errors;
}

async function stepCounter(page: Page): Promise<number> {
  const txt = await page.getByTestId('step-counter').innerText();
  const m = /Step (\d+)/.exec(txt);
  return m ? Number(m[1]) : -1;
}

/** Start from the landing page exactly as the presenter does. */
async function startLiveDemo(page: Page) {
  await page.goto('/#/');
  await expect(page.getByTestId('llm-badge')).toContainText('LLM');
  await page.getByTestId('reset-demo').click();
  await expect(page.getByTestId('toast')).toContainText('reset', { ignoreCase: true });
  await page.getByTestId('start-demo').click();
  await expect(page.getByTestId('step-counter')).toContainText('Step 0');
  // The autostart flag is consumed: Back/refresh must not reset the replay again.
  await expect(page).toHaveURL(/#\/replay$/);
}

/** Click Approve if an approval card is showing, otherwise Next, and wait for the step to finish. */
async function advance(page: Page) {
  const approve = page.getByTestId('approve-button');
  const stepDone = page.waitForResponse((r) => r.url().includes('/api/replay/step'));
  if (await approve.isVisible()) await approve.click();
  else await page.getByTestId('replay-next').click();
  await stepDone;
  await expect(page.getByTestId('replay-next')).toHaveAttribute('data-busy', 'false');
}

// Full historical replay: real 2025 observation → planner → OGI unavailable (re-rank) →
// repair claim REJECTED → verification → real 2026 observation REOPENS the case (RECURRING).
test('full Kanjur replay runs end to end, presenter-driven', async ({ page }) => {
  const consoleErrors = trackConsole(page);
  await startLiveDemo(page);

  // "Start live demo" must NOT autoplay: still on the intro after 5 s.
  await page.waitForTimeout(5000);
  expect(await stepCounter(page)).toBe(0);

  let sawRejectedInView = false;
  let sawOgiExcluded = false;
  const vh = page.viewportSize()?.height ?? 720;
  for (let i = 0; i < 25; i++) {
    if (await page.getByTestId('replay-done').isVisible()) break;
    await advance(page);
    const rejected = page.getByTestId('banner-rejected');
    if ((await rejected.count()) > 0) {
      // The show-stopper must be on screen without the presenter scrolling (wait for the smooth scroll).
      await expect
        .poll(async () => {
          const box = await rejected.boundingBox();
          return !!box && box.y >= 0 && box.y < vh;
        }, { timeout: 4000 })
        .toBe(true);
      sawRejectedInView = true;
    }
    if ((await page.getByTestId('replanned-badge').isVisible()) && (await page.getByTestId('excluded-ogi_survey').isVisible())) {
      sawOgiExcluded = true;
    }
  }
  await expect(page.getByTestId('replay-done')).toBeVisible();
  await expect(page.getByTestId('banner-reopened')).toBeVisible();
  expect(sawRejectedInView, 'closure-rejected banner appeared inside the viewport').toBe(true);
  expect(sawOgiExcluded, 'OGI survey excluded after re-rank').toBe(true);

  // The reopened case is visibly RECURRING on the case page.
  await page.goto('/#/cases/KJ-2025-02');
  await expect(page.getByTestId('status-pill').first()).toContainText(/Recurring/i);

  // The evaluation page shows computed results.
  await page.goto('/#/evaluation');
  await expect(page.getByTestId('metrics-table')).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId('metrics-table')).toContainText('PlumeProof');

  expect(consoleErrors, consoleErrors.join('\n')).toEqual([]);
});

// Human-in-the-loop is real: rejecting an approval stops the agent; approving the re-proposal continues.
test('rejecting an approval stops the replay until a human approves', async ({ page }) => {
  const consoleErrors = trackConsole(page);
  await startLiveDemo(page);

  // Step forward until the first approval card appears.
  for (let i = 0; i < 6 && !(await page.getByTestId('approve-button').isVisible()); i++) {
    await advance(page);
  }
  await expect(page.getByTestId('approve-button')).toBeVisible();
  const before = await stepCounter(page);

  const stepDone = page.waitForResponse((r) => r.url().includes('/api/replay/step'));
  await page.getByTestId('reject-button').click();
  await stepDone;
  await expect(page.getByTestId('replay-next')).toHaveAttribute('data-busy', 'false');

  await expect(page.getByTestId('banner-warning')).toContainText(/rejected/i);
  await expect(page.getByTestId('step-title')).toContainText(/Human rejected/i);
  expect(await stepCounter(page)).toBe(before); // the agent did not act
  await expect(page.getByTestId('approve-button')).toBeVisible(); // re-proposed item

  await advance(page); // approve the re-proposal
  expect(await stepCounter(page)).toBe(before + 1);
  await expect(page.getByTestId('banner-warning')).toHaveCount(0);

  expect(consoleErrors, consoleErrors.join('\n')).toEqual([]);
});
