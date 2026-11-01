import { test, expect } from '@playwright/test'

test('fresh browser opens workbench, scope and models without login', async ({ page }) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page).toHaveURL(/#\/chat\/index$/)
  await expect(page.getByRole('menubar').getByRole('menuitem')).toHaveText(['智能问数', '数据源', '模型设置'])
  await page.getByRole('menuitem', { name: '数据源', exact: true }).click()
  await expect(page).toHaveURL(/#\/ds\/index$/)
  await expect(page.locator('.card-content .card').first()).toBeVisible()
  await page.locator('.card-content .card').first().hover()
  const scope = page.getByRole('button', { name: '配置问数范围', exact: true }).first()
  await scope.click()
  await expect(page.getByText('允许问数的表和字段', { exact: true })).toBeVisible()
  await page.locator('.data-table .list-content .model').first().click()
  await expect(page.getByRole('switch', { name: '允许此表参与问数', exact: true }).locator('..')).toBeVisible()
  await expect(page.getByRole('switch', { name: /^允许查询字段：/ }).first().locator('..')).toBeVisible()
  await page.goto('/#/system/model')
  await expect(page.getByRole('menubar')).toBeVisible()
  await expect(page.getByRole('button', { name: '本地账号', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '本地账号', exact: true }).click()
  await expect(page.locator('.system-person:visible')).toBeVisible()
  await expect(page.locator('.system-person:visible .popover-item')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('local session uses original API auth and rejects cross-site bootstrap', async ({ request, baseURL }) => {
  const unauthenticated = await request.get('/api/v1/user/info')
  expect(unauthenticated.status()).toBe(401)
  const crossSite = await request.post('/api/v1/login/local-access-token', {
    headers: { Origin: 'https://cross-site.invalid', 'Sec-Fetch-Site': 'cross-site' }
  })
  expect(crossSite.status()).toBe(403)
  const session = await request.post('/api/v1/login/local-access-token', { headers: { Origin: baseURL } })
  expect(session.status()).toBe(200)
  expect(session.headers()['cache-control']).toContain('no-store')
  const result = await session.json()
  const profile = await request.get('/api/v1/user/info', {
    headers: { 'X-SQLBOT-TOKEN': `Bearer ${result.data.access_token}` }
  })
  expect(profile.status()).toBe(200)
  const user = (await profile.json()).data
  expect(String(user.id)).toBe('1')
  expect(String(user.oid)).toBe('1')
  expect(user.isAdmin).toBe(true)
})

for (const path of ['/login', '/admin-login']) {
  test(`old ${path} entry automatically enters workbench`, async ({ page }) => {
    await page.goto(`/#${path}`)
    await expect(page).toHaveURL(/#\/chat\/index$/)
    await expect(page.getByRole('menubar')).toBeVisible()
    await page.reload()
    await expect(page.getByRole('menubar')).toBeVisible()
  })
}

test('per-user permission page redirects to datasource scope in single-user mode', async ({ page }) => {
  await page.goto('/#/set/permission')
  await expect(page).toHaveURL(/#\/ds\/index$/)
  await expect(page.getByRole('menubar').getByRole('menuitem')).toHaveCount(3)
})

test('disabled local endpoint leaves ordinary login usable', async ({ page }) => {
  await page.route('**/login/local-access-token', route => route.fulfill({ status: 404, json: { detail: 'disabled' } }))
  await page.goto('/#/login')
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()
})
