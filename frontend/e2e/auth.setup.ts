import { test as setup, expect } from '@playwright/test'
import { STORAGE_STATE } from '../playwright.config'

setup('authenticate', async ({ page }) => {
  await page.goto('/login')
  await page.locator('#username').fill('admin')
  await page.locator('#password').fill('admin123')
  await page.getByRole('button', { name: /登录系统|Login/ }).click()

  // Wait for redirect to knowledge base page
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText('知识库管理').first()).toBeVisible()

  // Persist the JWT for Playwright. sessionStorage cannot be captured by
  // storageState, so we mirror it to a localStorage key that the auth store
  // also reads on startup.
  const token = await page.evaluate(() => window.sessionStorage.getItem('token'))
  if (token) {
    await page.evaluate((t) => window.localStorage.setItem('__playwright_token__', t), token)
  }

  // Ensure at least one knowledge base exists for downstream E2E tests.
  await page.evaluate(async (t) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (t) headers.Authorization = `Bearer ${t}`
    const listRes = await fetch('/api/v1/knowledge-bases', { headers })
    const list = await listRes.json()
    if (!Array.isArray(list) || list.length === 0) {
      await fetch('/api/v1/knowledge-bases', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          name: 'E2E Default KB',
          description: 'Auto-created by Playwright setup',
        }),
      })
    }
  }, token)

  await page.context().storageState({ path: STORAGE_STATE })
})
