import { expect, test } from '@playwright/test';

// Full historical replay: real 2025 observation → planner → OGI unavailable (re-rank) →
// repair claim REJECTED → verification → real 2026 observation REOPENS the case.
test('full Kanjur replay runs end to end', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && !/tile\.openstreetmap|Failed to load resource/i.test(msg.text())) consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  await page.goto('/#/');
  await expect(page.getByTestId('llm-badge')).toContainText('LLM');
  await page.getByTestId('reset-demo').click();
  await expect(page.getByTestId('toast')).toContainText('reset', { ignoreCase: true });

  await page.goto('/#/replay');
  await page.getByTestId('replay-reset').click();
  await expect(page.getByTestId('step-counter')).toContainText('Step 0');

  let sawRejected = false;
  let sawOgiExcluded = false;
  for (let i = 0; i < 25; i++) {
    if (await page.getByTestId('replay-done').isVisible()) break;
    const approve = page.getByTestId('approve-button');
    const stepDone = page.waitForResponse((r) => r.url().includes('/api/replay/step'));
    if (await approve.isVisible()) await approve.click();
    else await page.getByTestId('replay-next').click();
    // Wait for the step's API calls to finish (approving may surface a follow-up approval on the same step).
    await stepDone;
    await expect(page.getByTestId('replay-next')).toHaveAttribute('data-busy', 'false');
    const rejected = page.getByTestId('banner-rejected');
    if ((await rejected.count()) > 0 && /reject/i.test(await rejected.innerText())) sawRejected = true;
    if ((await page.getByTestId('replanned-badge').isVisible()) && (await page.getByTestId('excluded-ogi_survey').isVisible())) {
      sawOgiExcluded = true;
    }
  }
  await expect(page.getByTestId('replay-done')).toBeVisible();
  await expect(page.getByTestId('banner-reopened')).toBeVisible();
  expect(sawRejected, 'closure-rejected banner appeared').toBe(true);
  expect(sawOgiExcluded, 'OGI survey excluded after re-rank').toBe(true);

  // The evaluation page shows computed results.
  await page.goto('/#/evaluation');
  await expect(page.getByTestId('metrics-table')).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId('metrics-table')).toContainText('PlumeProof');

  expect(consoleErrors, consoleErrors.join('\n')).toEqual([]);
});
