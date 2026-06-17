import { test, expect } from '@playwright/test';

test.describe('Model Config', () => {
  test('updates embedding and rerank model config without clearing API keys', async ({ page }) => {
    await page.goto('/system-admin');
    await page.getByText('模型配置').click();
    await page.waitForSelector('text=模型服务配置');

    await page.getByLabel('Embedding API URL').fill('https://yunwu.ai/v1/embeddings');
    await page.getByLabel('Embedding 模型名').fill('text-embedding-3-large');
    await page.getByLabel('Re-rank API URL').fill('https://yunwu.ai/v1/rerank');
    await page.getByLabel('Re-rank 模型名').fill('qwen3-rerank');

    const savePromise = page.waitForResponse(
      (response) =>
        response.url().includes('/api/v1/config/models') &&
        response.request().method() === 'PUT',
      { timeout: 15000 }
    );
    await page.getByRole('button', { name: '保存配置' }).click();
    const response = await savePromise;
    expect(response.status()).toBe(200);
  });
});
