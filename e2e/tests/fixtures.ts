import { expect, type Page } from '@playwright/test';

export async function sendMessage(page: Page, text: string) {
  await page.getByRole('textbox', { name: 'Message' }).fill(text);
  await page.getByRole('button', { name: 'Send message' }).click();
}

export async function waitForReply(page: Page) {
  await expect(page.getByRole('button', { name: 'Send message' })).toBeVisible({ timeout: 15_000 });
}

export function lastAssistant(page: Page) {
  return page.getByRole('article', { name: 'Assistant message' }).last();
}
