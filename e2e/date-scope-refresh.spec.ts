import { expect, test } from '@playwright/test';

const csv = [
  'sale_date,division,net_sales,quantity',
  '2026-01-01,North,100,1',
  '2026-01-02,South,200,2',
  '2026-01-03,North,300,3',
  '2026-02-01,South,400,4',
].join('\n');

test('latest global date scope wins without unmounting the active workspace', async ({ page }) => {
  let delayedFirstScope = false;
  await page.route('**/executive-overview?*', async route => {
    const url = new URL(route.request().url());
    if (!delayedFirstScope && url.searchParams.get('start') === '2026-01-02') {
      delayedFirstScope = true;
      await new Promise(resolve => setTimeout(resolve, 700));
    }
    await route.continue();
  });

  await page.goto('/');
  await page.locator('input[type="file"]').setInputFiles({ name: 'scope.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await expect(page.getByRole('heading', { name: 'Executive Hub' })).toBeVisible();
  const scope = page.locator('[aria-label="Global date range"]');
  const from = scope.getByLabel('From');
  const to = scope.getByLabel('To');
  await expect(from).toHaveValue('2026-01-01');
  await expect(to).toHaveValue('2026-02-01');

  // A companion table belongs to a concrete executed chart. Turn the ranking
  // card into a bounded donut before changing the global scope.
  const rankingCard = page.locator('.executive-chart-card.role-ranking').first();
  await rankingCard.locator('select').nth(2).selectOption('donut');
  await expect(page.locator('.chart-companion-table').first()).toBeVisible();

  await from.fill('2026-01-02');
  await expect(page.locator('.workspace-grid')).toBeVisible();
  await expect(page.locator('.executive-chart-grid')).toBeVisible();
  await from.fill('2026-01-03');

  const expectedScope = JSON.stringify({ column: 'sale_date', start: '2026-01-03', end: '2026-02-01' });
  await expect(page.locator('section.space-y-3[data-applied-scope-key]')).toHaveAttribute('data-applied-scope-key', expectedScope);
  const companion = page.locator('.chart-companion-table').first();
  await expect(companion).toBeVisible();
  await expect(companion).toHaveAttribute('data-applied-scope-key', expectedScope);
  await expect(companion).toContainText('Scope total');
  await expect(companion.getByText('Scope total', { exact: true })).toBeVisible();
  await expect(page.locator('.workspace-grid')).toBeVisible();
  await expect(page.locator('.executive-chart-grid')).toBeVisible();
});
