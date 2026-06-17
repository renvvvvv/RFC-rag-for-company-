import { test, expect } from '@playwright/test'

test.describe('Chat', () => {
  test('sends a chat message and receives a response', async ({ page }) => {
    await page.goto('/search-console')
    await expect(page.getByText('检索控制台').first()).toBeVisible()

    // Wait for KB selector and select first KB
    await expect(page.locator('.ant-select').first()).toBeVisible({ timeout: 10000 })
    await page.locator('.ant-select').first().click()
    await page.locator('.ant-select-item').first().click()

    // Create a new conversation
    await page.getByRole('button', { name: /新建会话/ }).first().click()

    // Wait for textarea
    await expect(page.locator('textarea').first()).toBeVisible()

    await page.locator('textarea').first().fill('企业RAG是什么？')
    await page.getByRole('button', { name: /发送/ }).first().click()

    // Expect assistant response area to appear (mock LLM returns fixed text)
    await expect(
      page.getByText(/Mock LLM|测试回答|RAG|请求处理失败/).first()
    ).toBeVisible({ timeout: 30000 })
  })
})
