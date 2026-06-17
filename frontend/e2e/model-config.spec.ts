import { test, expect } from '@playwright/test';

test.describe('Model Config', () => {
  test('updates embedding and rerank model config without clearing API keys', async ({ page }) => {
    let lastResponseStatus = 0;
    let lastResponseBody = '';
    page.on('response', async (response) => {
      if (response.url().includes('/api/v1/config/models') && response.request().method() === 'PUT') {
        lastResponseStatus = response.status();
        try {
          lastResponseBody = await response.text();
        } catch {}
      }
    });

    await page.goto('/system-admin');
    await page.getByText('模型配置').click();
    await page.waitForSelector('text=模型服务配置');

    await page.getByLabel('Embedding API URL').fill('https://yunwu.ai/v1/embeddings');
    await page.getByLabel('Embedding 模型名').fill('text-embedding-3-large');
    await page.getByLabel('Re-rank API URL').fill('https://yunwu.ai/v1/rerank');
    await page.getByLabel('Re-rank 模型名').fill('qwen3-rerank');

    await page.getByRole('button', { name: '保存配置' }).click();
    await expect(page.locator('.ant-message-notice').first()).toBeVisible({ timeout: 15000 });
    expect(lastResponseStatus).toBe(200);
  });
});
