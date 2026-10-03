import { expect, test } from '@playwright/test';

import { lastAssistant, sendMessage, waitForReply } from './fixtures';

// 1x1 red PNG
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==', 'base64');

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

test('upload a document, summarise it and ask a follow-up question', async ({ page }) => {
  await page.getByTestId('file-input').setInputFiles({
    name: 'policy.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Employees receive 25 days of annual leave per year.'),
  });
  await expect(page.getByRole('list', { name: 'Attachments' })).toContainText('policy.txt');
  await sendMessage(page, 'Summarize this document');
  await waitForReply(page);
  await expect(lastAssistant(page)).toContainText('Summary:');

  await sendMessage(page, 'How many leave days do employees get?');
  await waitForReply(page);
  await expect(lastAssistant(page)).toContainText('Based on the document');
});

test('analyse multiple files independently', async ({ page }) => {
  await page.getByTestId('file-input').setInputFiles([
    { name: 'a.md', mimeType: 'text/markdown', buffer: Buffer.from('# Alpha') },
    { name: 'b.csv', mimeType: 'text/csv', buffer: Buffer.from('x,y\n1,2') },
  ]);
  await expect(page.getByRole('list', { name: 'Attachments' }).getByRole('listitem')).toHaveCount(2);
  await sendMessage(page, 'Summarize each file');
  await waitForReply(page);
  await expect(page.getByRole('article', { name: 'Your message' }).last()).toContainText('a.md');
});

test('upload and analyse an image with the vision capability', async ({ page }) => {
  await page.getByTestId('file-input').setInputFiles({ name: 'dot.png', mimeType: 'image/png', buffer: PNG });
  await sendMessage(page, 'What is in this picture?');
  await waitForReply(page);
  await expect(lastAssistant(page).locator('.route-badge')).toContainText('Vision');
  await expect(lastAssistant(page)).toContainText('Mock vision analysis');
});
