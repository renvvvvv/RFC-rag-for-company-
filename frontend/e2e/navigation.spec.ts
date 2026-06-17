import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('navigates through main pages from sidebar/menu', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('知识库管理').first()).toBeVisible()

    const routes = [
      { path: '/upload-center', text: '上传中心' },
      { path: '/search-console', text: '检索控制台' },
      { path: '/eval-workbench', text: '评测工作台' },
      { path: '/permission-mgr', text: '权限管理' },
      { path: '/system-admin', text: '系统管理' },
      { path: '/product', text: '产品方案' },
    ]

    for (const route of routes) {
      await page.goto(route.path)
      await expect(page.getByText(route.text).first()).toBeVisible({ timeout: 10000 })
    }
  })

  test('logs out and redirects to login', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('知识库管理').first()).toBeVisible()

    await page.getByRole('button', { name: /退出/ }).click()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.locator('#username')).toBeVisible()
  })
})
