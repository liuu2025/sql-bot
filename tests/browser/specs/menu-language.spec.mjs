import { test, expect } from '@playwright/test'

const entries = ['智能问数', '数据源', '模型设置', '权限配置']
const labels = page => page.getByRole('menubar').getByRole('menuitem')

test('本地账号在问数、模型与权限页面共用四项中文导航', async ({ page }) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await page.evaluate(() => window.menuFixture.signIn({ id: 1, language: 'zh-CN', weight: 1 }))
  for (const path of ['/chat/index', '/system/model', '/set/permission']) {
    await page.evaluate(target => window.menuFixture.go(target), path)
    await expect(labels(page)).toHaveText(entries)
  }
  expect(errors).toEqual([])
})

test('退出和切换账号后按现有权限收紧入口，不沿用上个账号的导航', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => window.menuFixture.signIn({ id: 1, language: 'zh-CN', weight: 1 }))
  await expect(labels(page)).toHaveText(entries)
  await page.evaluate(() => window.menuFixture.signOut())
  await expect(page.getByRole('menubar')).toHaveCount(0)
  await page.evaluate(() => window.menuFixture.signIn({ id: 43, language: 'zh-CN', weight: 0 }))
  await expect(labels(page)).toHaveText(['智能问数'])
  await page.evaluate(() => window.menuFixture.signIn({ id: 42, language: 'zh-CN', weight: 1 }))
  await expect(labels(page)).toHaveText(['智能问数', '数据源', '权限配置'])
})

test('查询优化页面已移除，其他注册路由不自动成为导航项', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => window.menuFixture.signIn({ id: 1, language: 'en', weight: 1 }))
  await expect(page.locator('#language')).toHaveText('zh-CN')
  await page.evaluate(() => window.menuFixture.go('/set'))
  await expect(page).toHaveURL(/#\/set\/permission$/)
  expect(await page.evaluate(() => window.menuFixture.currentPath())).toBe('/set/permission')
  await expect(labels(page)).toHaveText(entries)
  await page.evaluate(() => window.menuFixture.go('/extension'))
  await expect(labels(page)).toHaveText(entries)
  await expect(page.getByText('Extension title', { exact: true })).toHaveCount(0)
})
