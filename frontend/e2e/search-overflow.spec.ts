import { test, expect } from '@playwright/test'

test.describe('Search Console Overflow', () => {
  test('long assistant answer does not overflow the chat card', async ({ page }) => {
    // Mock the chat endpoint so we don't depend on the real LLM being fast.
    await page.route('/api/v1/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer:
            '这是一个非常长的回答，用于验证长文本不会溢出聊天卡片。' +
            '**多模态接入**：支持多种数据类型，如文档、表格、图片、视频、音频和网页链接。' +
            '统一检索：结合向量检索和BM25算法，能够召回高相关的内容。' +
            'RAG（Retrieval-Augmented Generation）是一种企业级私有化的多模态知识检索与生成系统，' +
            '主要面向金融、制造、政务、能源等行业。' +
            'https://example.com/very/long/url/that/should/not/overflow/the/message/bubble/endpoint',
          sources: [
            {
              doc_id: 'doc-1',
              chunk_id: 'chunk-1',
              content: 'source content',
              score: 0.95,
              modality: 'text',
            },
          ],
          intercepted: false,
        }),
      })
    })

    await page.goto('/search-console')
    await expect(page.getByText('检索控制台').first()).toBeVisible()

    // Select the first knowledge base
    await expect(page.locator('.ant-select').first()).toBeVisible({ timeout: 10000 })
    await page.locator('.ant-select').first().click()
    await page.locator('.ant-select-item').first().click()

    await page.locator('textarea').first().fill('overflow-test')
    await page.getByRole('button', { name: /发送/ }).first().click()

    // Wait for the assistant message to render
    const assistantMessage = page.locator('.ant-list-item').last()
    await expect(assistantMessage).toContainText('多模态接入', { timeout: 10000 })

    // The message bubble must stay inside the chat card / viewport
    const bubble = assistantMessage.locator('div').first()
    const box = await bubble.boundingBox()
    const viewport = page.viewportSize()
    expect(box).not.toBeNull()
    if (box && viewport) {
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(viewport.width)
    }

  })
})
