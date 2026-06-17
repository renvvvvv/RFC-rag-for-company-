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

  await page.context().storageState({ path: STORAGE_STATE })
})
