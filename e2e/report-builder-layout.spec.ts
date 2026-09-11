import { expect, Page, test } from '@playwright/test';

const csv = [
  'sale_date,division,net_sales,quantity',
  '2026-01-01,North,100,1',
  '2026-01-02,South,200,2',
  '2026-02-01,North,300,3',
].join('\n');

async function openBuilder(page: Page) {
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
}

test('keeps template blocks inside the canvas and outside the inspector', async ({ page }) => {
  await openBuilder(page);

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

test('selecting a block does not move it away from the click point', async ({ page }) => {
  await openBuilder(page);
  await page.waitForTimeout(500);
  const blocks = page.locator('.report-block');
  const count = await blocks.count();
  expect(count).toBeGreaterThan(0);

  for (let index = 0; index < count; index += 1) {
    const block = blocks.nth(index);
    await block.scrollIntoViewIfNeeded();
    const before = await block.boundingBox();
    expect(before).not.toBeNull();
    if (!before) continue;
    await block.click({ position: { x: Math.min(24, before.width / 2), y: Math.min(48, Math.max(34, before.height / 2)) } });
    const after = await block.boundingBox();
    expect(after).not.toBeNull();
    if (!after) continue;
    expect(after.x).toBeCloseTo(before.x, 0);
    expect(after.y).toBeCloseTo(before.y, 0);
    await expect(block).toHaveClass(/selected/);
  }
});
