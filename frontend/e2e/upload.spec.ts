import { test, expect } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

test.describe('Upload Center', () => {
  test('uploads a sample document to the first knowledge base', async ({ page }) => {
    await page.goto('/upload-center')
    await expect(page.getByText('上传中心').first()).toBeVisible()

    // Wait for KB selector to populate and pick first option if not already selected
    await expect(page.locator('.ant-select').first()).toBeVisible()

    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.locator('.ant-upload-drag').click()
    const fileChooser = await fileChooserPromise

    const samplePath = path.join(__dirname, '../../samples/01-企业RAG产品介绍.md')
    await fileChooser.setFiles(samplePath)

    // Wait for file to appear in upload list
    await expect(page.locator('.ant-upload-list-item').first()).toBeVisible({ timeout: 10000 })

    // Trigger upload
    await page.getByRole('button', { name: /开始上传|上传|开始/ }).click()

    // Wait for success message or document list update
    await expect(page.getByText(/上传成功|success/i).first()).toBeVisible({ timeout: 20000 })

    // Document list should refresh and show a row
    await expect(page.locator('.ant-table-row').first()).toBeVisible({ timeout: 10000 })
  })
})
