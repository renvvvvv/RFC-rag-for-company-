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

    // The Dragger uses customRequest so the file uploads immediately on selection.
    // Wait for the file to appear in the upload list and then the document table.
    await expect(page.locator('.ant-upload-list-item').first()).toBeVisible({ timeout: 10000 })
    await expect(page.locator('.ant-table-row').first()).toBeVisible({ timeout: 20000 })
  })
})
