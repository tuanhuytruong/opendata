import { expect, test } from '@playwright/test';

const csv = [
  'sale_date,division,net_sales,quantity',
  '2026-01-01,North,100,1',
  '2026-01-02,South,200,2',
  '2026-02-01,North,300,3',
].join('\n');

test('keeps template blocks inside the canvas and outside the inspector', async ({ page }) => {
  await page.goto('/');
  await page.locator('input[type="file"]').setInputFiles({
    name: 'report-builder-layout.csv', mimeType: 'text/csv', buffer: Buffer.from(csv),
  });
  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Custom Report' }).click();
  await expect(page.locator('.report-builder')).toBeVisible();

  page.once('dialog', dialog => void dialog.accept());
  await page.locator('.template-choice').first().click();
  await expect(page.locator('.report-save-saved')).toBeVisible();

  const canvasArea = await page.locator('.report-canvas-area').boundingBox();
  const inspector = await page.locator('.report-inspector').boundingBox();
  expect(canvasArea).not.toBeNull();
  expect(inspector).not.toBeNull();
  if (!canvasArea || !inspector) return;
  expect(canvasArea.x + canvasArea.width).toBeLessThanOrEqual(inspector.x + 1);

  for (const block of await page.locator('.report-block').all()) {
    const box = await block.boundingBox();
    expect(box).not.toBeNull();
    if (!box) continue;
    expect(box.x).toBeGreaterThanOrEqual(canvasArea.x - 1);
    expect(box.x + box.width).toBeLessThanOrEqual(canvasArea.x + canvasArea.width + 1);
  }
});
