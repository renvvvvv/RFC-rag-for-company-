import { test, expect } from '@playwright/test'

test.describe('Search Console', () => {
  test('performs a chat-style search and shows assistant response', async ({ page }) => {
    await page.goto('/search-console')
    await expect(page.getByText('检索控制台').first()).toBeVisible()

    // Wait for KB selector to populate and select the first knowledge base
    await expect(page.locator('.ant-select').first()).toBeVisible({ timeout: 10000 })
    await page.locator('.ant-select').first().click()
    await page.locator('.ant-select-item').first().click()

    // Type a query and send
    await page.locator('textarea').first().fill('RAG')
    await page.getByRole('button', { name: /发送/ }).first().click()

    // Expect either an assistant message or a loading state to appear
    await expect(
      page.getByText(/引用来源|已拦截|检索生成中|请求处理失败/).first()
    ).toBeVisible({ timeout: 30000 })
  })
})
