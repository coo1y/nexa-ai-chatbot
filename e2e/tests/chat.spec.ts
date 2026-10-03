import { expect, test } from '@playwright/test';

import { lastAssistant, sendMessage, waitForReply } from './fixtures';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test('anonymous user chats with streamed responses, regenerates, edits and rates', async ({ page }) => {
  await expect(page.getByRole('heading', { name: 'How can I help today?' })).toBeVisible();

  await sendMessage(page, 'Hello Nexa');
  await waitForReply(page);
  await expect(lastAssistant(page)).toContainText('Mock response to: Hello Nexa');
  await expect(lastAssistant(page).locator('.route-badge')).toContainText('Fast');

  await page.getByRole('button', { name: 'Regenerate response' }).click();
  await waitForReply(page);
  await expect(page.getByRole('article', { name: 'Assistant message' })).toHaveCount(1);

  await page.getByRole('article', { name: 'Your message' }).hover();
  await page.getByRole('button', { name: 'Edit message' }).click();
  await page.getByRole('textbox', { name: 'Edit message' }).fill('Hello again');
  await page.getByRole('button', { name: /Save/ }).click();
  await waitForReply(page);
  await expect(lastAssistant(page)).toContainText('Mock response to: Hello again');

  await page.getByRole('button', { name: 'Good response' }).click();
  await expect(page.getByRole('button', { name: 'Good response' })).toHaveAttribute('aria-pressed', 'true');
});

test('coding question renders a highlighted code block', async ({ page }) => {
  await sendMessage(page, 'Write a python function that adds two numbers');
  await waitForReply(page);
  await expect(lastAssistant(page).locator('.code-block')).toContainText('def add');
});

test('utility tools stream their activity', async ({ page }) => {
  await sendMessage(page, 'Please calculate (17 + 3) * 2.5');
  await waitForReply(page);
  await expect(page.getByTestId('tool-activity')).toContainText('(17 + 3) * 2.5 = 50');

  await sendMessage(page, 'Convert 5 miles to km');
  await waitForReply(page);
  await expect(page.getByTestId('tool-activity').last()).toContainText('5 miles = 8.04672 km');
});

test('web search shows citations and the sources panel', async ({ page }) => {
  await page.getByRole('button', { name: /Search/ }).click();
  await sendMessage(page, 'best hiking trails in Chiang Mai');
  await waitForReply(page);
  await expect(page.getByTestId('tool-activity')).toContainText('Found 3 results');
  await lastAssistant(page).getByRole('button', { name: 'Show source 1' }).click();
  const panel = page.getByRole('complementary', { name: 'Sources' });
  await expect(panel.getByRole('link')).toHaveCount(3);
  await expect(panel.getByRole('link').first()).toHaveAttribute('href', /example\.com/);
});

test('automatic search triggers for time-sensitive questions', async ({ page }) => {
  await sendMessage(page, "What are today's top headlines?");
  await waitForReply(page);
  await expect(page.getByTestId('tool-activity')).toContainText('Web search');
  await expect(lastAssistant(page).getByRole('button', { name: /sources/ })).toBeVisible();
});

test('user can stop an active generation', async ({ page }) => {
  await sendMessage(page, '[[mock:slow]] write a very long story about a dragon and a knight');
  await page.getByRole('button', { name: 'Stop generating' }).click();
  await expect(page.getByText('Generation stopped.')).toBeVisible();
});

test('failed requests show a friendly error with Retry', async ({ page }) => {
  await sendMessage(page, 'this fails [[mock:fail]]');
  await waitForReply(page);
  const alert = page.getByRole('alert');
  await expect(alert).toContainText('temporarily unavailable');
  await expect(alert).not.toContainText('mock');
  await expect(alert.getByRole('button', { name: /Retry/ })).toBeVisible();
});

test('manual capability selection is honoured', async ({ page }) => {
  await page.getByRole('radio', { name: /Reasoning/ }).click();
  await sendMessage(page, 'hi');
  await waitForReply(page);
  await expect(lastAssistant(page).locator('.route-badge')).toHaveText(/Reasoning\s*selected/);
});
