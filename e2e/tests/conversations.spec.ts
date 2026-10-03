import { expect, test } from '@playwright/test';

import { sendMessage, waitForReply } from './fixtures';

test('conversations are stored locally and can be renamed and deleted', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  const sidebar = page.getByRole('navigation', { name: 'Conversations' });

  await sendMessage(page, 'Trip planning');
  await waitForReply(page);
  await page.getByRole('button', { name: 'New chat' }).click();
  await sendMessage(page, 'Recipe ideas');
  await waitForReply(page);

  await page.reload();
  await expect(sidebar.getByText('Trip planning')).toBeVisible();
  await expect(sidebar.getByText('Recipe ideas')).toBeVisible();

  await sidebar.getByText('Trip planning').hover();
  await sidebar.getByRole('button', { name: 'Rename Trip planning' }).click();
  await sidebar.getByRole('textbox', { name: 'Conversation title' }).fill('Japan 2027');
  await sidebar.getByRole('textbox', { name: 'Conversation title' }).press('Enter');
  await expect(sidebar.getByText('Japan 2027')).toBeVisible();

  await sidebar.getByText('Recipe ideas').hover();
  await sidebar.getByRole('button', { name: 'Delete Recipe ideas' }).click();
  await sidebar.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(sidebar.getByText('Recipe ideas')).toHaveCount(0);

  await page.reload();
  await expect(sidebar.getByText('Japan 2027')).toBeVisible();
  await expect(sidebar.getByText('Recipe ideas')).toHaveCount(0);
});

test('light and dark themes', async ({ page }) => {
  await page.goto('/');
  const html = page.locator('html');
  const initial = await html.getAttribute('data-theme');
  await page.getByRole('button', { name: 'Toggle theme' }).click();
  await expect(html).not.toHaveAttribute('data-theme', initial ?? '');
  await page.screenshot({ path: 'test-results/theme-toggled.png' });
});
