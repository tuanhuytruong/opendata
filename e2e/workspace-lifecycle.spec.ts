import { expect, test } from '@playwright/test';

const csv = [
  'sale_date,division,net_sales,quantity',
  '2026-01-01,North,100,1',
  '2026-01-02,South,200,2',
  '2026-02-01,North,300,3',
].join('\n');

test('keeps the profiling shell isolated until the completed workspace is ready', async ({ page }) => {
  await page.goto('/');
  const health = await page.request.get('/api/health');
  const healthBody = await health.json() as { status: string; build_sha: string };
  expect(healthBody.status).toBe('ok');
  expect(healthBody.build_sha).toBe(await page.locator('html').getAttribute('data-build-sha'));
  await expect(page.getByRole('heading', { name: 'Bring your dataset' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-build-sha', /.+/);
  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toHaveCount(0);

  await page.route('**/profile/status', async route => {
    await new Promise(resolve => setTimeout(resolve, 250));
    await route.continue();
  });
  await page.locator('input[type="file"]').setInputFiles({ name: 'scope.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await expect(page.getByRole('heading', { name: 'Your workspace is taking shape.' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toHaveCount(0);
  await page.unroute('**/profile/status');

  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Executive Hub' })).toBeVisible();
  await expect(page.locator('.workspace-grid')).toBeVisible();
  await expect(page.locator('.executive-chart-grid')).toBeVisible();
});
