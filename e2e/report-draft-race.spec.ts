import { expect, test } from '@playwright/test';

const csv = [
  'sale_date,division,net_sales,quantity',
  '2026-01-01,North,100,1',
  '2026-01-02,South,200,2',
  '2026-02-01,North,300,3',
].join('\n');

test('does not let a completed report save overwrite a newer local draft', async ({ page }) => {
  await page.goto('/');
  await page.locator('input[type="file"]').setInputFiles({
    name: 'report-race.csv', mimeType: 'text/csv', buffer: Buffer.from(csv),
  });
  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Custom Report' }).click();
  const title = page.locator('.report-editor input').first();
  await expect(title).toBeVisible();

  let releaseSave: (() => void) | undefined;
  await page.route('**/api/runs/*/custom-report', async route => {
    if (route.request().method() !== 'PUT') return route.continue();
    await new Promise<void>(resolve => { releaseSave = resolve; });
    await route.continue();
  });
  await title.fill('Draft A');
  await title.blur();
  await expect.poll(() => Boolean(releaseSave)).toBe(true);
  await title.fill('Draft B');
  releaseSave?.();
  await expect(title).toHaveValue('Draft B');
});
