import { test, expect } from '@playwright/test'

test.describe('Knowledge Base Documents', () => {
  test('opens document list modal from knowledge base table', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('知识库管理').first()).toBeVisible()

    // Wait for the knowledge base table
    await expect(page.locator('.ant-table-row').first()).toBeVisible({ timeout: 10000 })

    // Click "查看文档" on the first knowledge base
    await page.getByRole('button', { name: '查看文档' }).first().click()

    // Document list modal should appear
    await expect(page.getByText('文档列表').first()).toBeVisible({ timeout: 10000 })

    // The document table should load (empty or with rows)
    await expect(page.locator('.ant-modal .ant-table').first()).toBeVisible()
  })
})
