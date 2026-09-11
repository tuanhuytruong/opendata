import { expect, test } from '@playwright/test';

const csv = [
  'sale_date,division,net_sales,quantity',
  '2026-01-01,North,100,1',
  '2026-01-02,South,200,2',
].join('\n');

test('keeps the report draft and exposes Retry after a text/plain save failure', async ({ page }) => {
  await page.goto('/');
  await page.locator('input[type="file"]').setInputFiles({
    name: 'report-error.csv', mimeType: 'text/csv', buffer: Buffer.from(csv),
  });
  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Custom Report' }).click();
  const title = page.locator('.report-name-input').first();
  await expect(title).toBeVisible();

  await page.route('**/api/runs/*/custom-report/v2', async route => {
    if (route.request().method() === 'PUT') {
      await route.fulfill({ status: 500, contentType: 'text/plain', body: 'Internal Server Error' });
      return;
    }
    await route.continue();
  });
  await title.fill('Draft survives failure');
  await title.blur();
  await expect(page.getByText('Request failed (500): Internal Server Error')).toBeVisible();
  await expect(title).toHaveValue('Draft survives failure');
  const retry = page.getByRole('button', { name: 'Save' });
  await expect(retry).toBeVisible();

  await page.unroute('**/api/runs/*/custom-report/v2');
  await retry.click();
  await expect(page.getByText('Saved', { exact: true })).toBeVisible();
  await expect(title).toHaveValue('Draft survives failure');
});
