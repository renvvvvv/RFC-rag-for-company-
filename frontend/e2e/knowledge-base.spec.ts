import { test, expect } from '@playwright/test'

test.describe('Knowledge Base', () => {
  test('lists knowledge bases and creates a new one', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('知识库管理').first()).toBeVisible()

    // The table should eventually load
    await expect(page.locator('.ant-table-row').first()).toBeVisible({ timeout: 10000 })

    const kbName = `E2E KB ${Date.now()}`

    // Capture current count from the list header tag
    const countText = await page.locator('.ant-card-head-title .ant-tag').first().textContent()
    const initialCount = parseInt(countText || '0', 10)

    // Open create modal
    await page.getByRole('button', { name: /新建知识库|创建知识库|新建/ }).click()
    await expect(page.locator('.ant-modal').getByText(/新建知识库|创建知识库/)).toBeVisible()

    await page.locator('.ant-modal').getByPlaceholder('例如：产品手册知识库').fill(kbName)
    await page.locator('.ant-modal').getByPlaceholder('简要描述知识库用途').fill('Created by Playwright E2E')

    await page.locator('.ant-modal').getByRole('button', { name: /确定|创建|OK/ }).click()

    // Wait for modal to close and table to refresh; assert count increased
    await expect(page.locator('.ant-modal')).not.toBeVisible({ timeout: 10000 })
    await expect(page.locator('.ant-card-head-title .ant-tag').first()).toHaveText(String(initialCount + 1), { timeout: 15000 })
  })
})
