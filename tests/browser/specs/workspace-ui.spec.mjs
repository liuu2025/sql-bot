import { test, expect } from '@playwright/test'

test('登录页展示中文项目说明和账号入口', async ({ page }) => {
  await page.goto('/#/login')
  await expect(page.getByText('数析 · 数据工作空间', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()

})

test.describe('已登录工作空间（真实导航，模型和数据配置使用合成响应）', () => {
  test.skip(!process.env.PLAYWRIGHT_STORAGE_STATE, '需提供本地登录状态文件')
  test.use({ storageState: process.env.PLAYWRIGHT_STORAGE_STATE || undefined })

  test('澄清在聊天内展示日期选项，点击补齐条件且历史卡片不可重复点击', async ({ page }) => {
    const reply = {
      kind: 'clarify', message: '你想查询哪个月的25号？当前可查询日期范围为2026-04-01至2026-09-28。',
      options: [
        { label: '2026年4月25日', question: '查25号详情\n补充条件：查询日期明确为2026-04-25，只查询这一天。' },
        { label: '2026年9月25日', question: '查25号详情\n补充条件：查询日期明确为2026-09-25，只查询这一天。' },
        { label: '所有月份的25号', question: '查询所有月份的25号，不限定月份。' }
      ]
    }
    const resultReply = { kind: 'result', message: '查询完成，返回2条结果。', options: [] }
    const records = [{ id: 99002, chat_id: 99001, question: '查25号详情', create_time: '2026-10-29T00:00:00',
      datasource: 98001, finish: true, first_chat: false, data: { _conversation_reply: reply } }]
    let requestCount = 0
    await page.route('**/api/v1/chat/**', async route => {
      const path = new URL(route.request().url()).pathname
      let data
      if (path.endsWith('/chat/list')) data = [{ id: 99001, brief: '日期澄清测试', datasource: 98001, create_time: records[0].create_time }]
      else if (path.endsWith('/chat/99001')) data = { id: 99001, brief: '日期澄清测试', datasource: 98001,
        datasource_name: '合成订单', datasource_exists: true, records }
      else if (path.endsWith('/record/99002/data')) data = { fields: [], data: [], _conversation_reply: reply }
      else if (path.endsWith('/record/99003/data')) data = { fields: ['order_count'], data: [{ order_count: 2 }], _conversation_reply: resultReply }
      else if (path.endsWith('/usage')) data = { steps: [], total_tokens: 0, duration: 0 }
      else if (path.endsWith('/chat/question')) {
        const request = route.request().postDataJSON()
        expect(request.question).toContain('2026-09-25')
        requestCount++
        records.push({ id: 99003, chat_id: 99001, question: request.question,
          create_time: '2026-10-29T00:01:00', datasource: 98001, finish: true, first_chat: false,
          data: { _conversation_reply: resultReply } })
        const events = [
          { type: 'id', id: 99003 }, { type: 'question', question: request.question },
          { type: 'reply', content: resultReply }, { type: 'finish' }
        ].map(event => `data:${JSON.stringify(event)}\n\n`).join('')
        return route.fulfill({ status: 200, contentType: 'text/event-stream', body: events })
      } else return route.fallback()
      return route.fulfill({ json: { code: 0, data, msg: '' } })
    })
    await page.goto('/#/chat/index')
    await page.getByText('日期澄清测试', { exact: true }).click()
    await expect(page.getByText('请补充查询条件', { exact: true })).toBeVisible()
    const choice = page.getByRole('button', { name: '2026年9月25日', exact: true })
    await expect(choice).toBeEnabled()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await choice.click()
    await expect.poll(() => requestCount).toBe(1)
    await expect(page.getByText('查询完成，返回2条结果。', { exact: true })).toBeVisible()
    await expect(choice).toBeDisabled()
    await page.reload()
    await page.getByText('日期澄清测试', { exact: true }).click()
    await expect(page.getByRole('button', { name: '2026年9月25日', exact: true })).toBeDisabled()
    await expect(page.getByText('查询完成，返回2条结果。', { exact: true })).toBeVisible()
    await page.screenshot({ path: 'output/conversation-date-clarification.png', animations: 'disabled' })
  })

  test('管理员可保存表字段问数范围，失败时恢复开关状态', async ({ page }) => {
    const ds = { id: 98001, oid: 1, name: '权限测试数据', type: 'pg', type_name: 'PostgreSQL', num: '1/1', description: '合成数据', configuration: '{}' }
    const table = { id: 98002, ds_id: ds.id, table_name: 'orders', checked: true, custom_comment: '演示订单' }
    const fields = [
      { id: 98003, ds_id: ds.id, table_id: table.id, field_name: 'amount', field_type: 'INTEGER', checked: true, custom_comment: '金额' },
      { id: 98004, ds_id: ds.id, table_id: table.id, field_name: 'phone', field_type: 'TEXT', checked: false, custom_comment: '手机号' }
    ]
    let failNext = false
    let savedFields = 0
    await page.route('**/api/v1/datasource/**', async route => {
      const path = new URL(route.request().url()).pathname
      let data
      if (path.endsWith('/list')) data = [ds]
      else if (path.endsWith(`/get/${ds.id}`)) data = ds
      else if (path.endsWith(`/tableList/${ds.id}`)) data = [table]
      else if (path.includes('/fieldList/')) data = fields
      else if (path.includes('/previewData/')) data = { fields: ['amount'], data: [{ amount: 129.99 }] }
      else if (path.endsWith('/editField')) {
        if (failNext) { failNext = false; return route.fulfill({ json: { code: 1, data: null, msg: '模拟保存失败' } }) }
        const value = route.request().postDataJSON()
        Object.assign(fields.find(field => field.id === value.id), value)
        savedFields++
        data = null
      } else if (path.endsWith('/editTable')) {
        Object.assign(table, route.request().postDataJSON())
        data = null
      } else return route.fallback()
      return route.fulfill({ json: { code: 0, data, msg: '' } })
    })
    const open = async () => {
      await page.goto('/#/ds/index')
      const card = page.locator('.connection-card').filter({ hasText: ds.name })
      await card.hover()
      await card.getByRole('button', { name: '配置问数范围', exact: true }).click()
      await page.getByText('orders', { exact: true }).click()
    }
    await open()
    await expect(page.getByText('允许问数的表和字段', { exact: true })).toBeVisible()
    const phone = page.getByRole('switch', { name: '允许查询字段：phone', exact: true })
    const allowTable = page.getByRole('switch', { name: '允许此表参与问数', exact: true })
    await expect(phone).not.toBeChecked()
    await phone.locator('..').click()
    await expect.poll(() => savedFields).toBe(1)
    await expect(phone).toBeChecked()
    await page.reload()
    await page.getByText(ds.name, { exact: true }).click()
    await page.getByText('orders', { exact: true }).click()
    await expect(phone).toBeChecked()
    failNext = true
    await phone.locator('..').click()
    await expect(page.getByText('保存失败，已恢复原设置，请重试。', { exact: true })).toBeVisible()
    await expect(phone).toBeChecked()
    expect(fields[1].checked).toBe(true)
    await allowTable.locator('..').click()
    await expect(allowTable).not.toBeChecked()
    await expect(phone).toBeDisabled()
    expect(table.checked).toBe(false)
    await page.screenshot({ path: 'output/sql-query-scope-desktop.png', animations: 'disabled' })
  })

  test('本地账号菜单只提供改密和退出，不显示管理与集成入口', async ({ page }) => {
    const licenseRequests = []
    page.on('request', request => {
      const path = new URL(request.url()).pathname
      // Runtime permission checks remain; the removed dialog queried the version
      // and exposed license updates. Neither should run from the account menu.
      if (path === '/api/v1/system/license/version' ||
          (path === '/api/v1/system/license' && request.method() === 'POST')) {
        licenseRequests.push(request.url())
      }
    })
    await page.goto('/#/chat/index')
    await expect(page.locator('button.person')).toHaveText('本地账号')
    await page.locator('button.person').click()
    const menu = page.locator('.system-person:visible')
    await expect(menu.getByText('修改密码', { exact: true })).toBeVisible()
    await expect(menu.getByText('退出登录', { exact: true })).toBeVisible()
    await expect(menu.getByText(/^(关于|帮助|About|Help|API Key|系统管理|Administrator)$/)).toHaveCount(0)
    await expect(page.getByRole('dialog', { name: '关于', exact: true })).toHaveCount(0)
    expect(licenseRequests).toEqual([])
    await page.screenshot({ path: 'output/sql-account-menu-desktop.png' })
  })

  test('四个主入口保持一致并使用权限配置入口', async ({ page }) => {
    const entries = ['智能问数', '数据源', '模型设置', '权限配置']
    const nav = page.locator('.navigation').getByRole('menuitem')
    await page.goto('/#/chat/index')
    await expect(nav).toHaveText(entries)
    await expect(page.locator('.workspace-header')).not.toContainText('系统管理员')
    await expect(page.locator('.left-side')).not.toContainText('默认工作空间')
    await page.getByRole('menuitem', { name: '模型设置', exact: true }).click()
    await expect(nav).toHaveText(entries)
    await expect(page.getByText('授权工作空间', { exact: true })).toHaveCount(0)
    await page.getByRole('menuitem', { name: '权限配置', exact: true }).click()
    await expect(page.getByRole('heading', { name: '权限配置' })).toBeVisible()
    await expect(page.getByRole('menuitem', { name: '查询优化' })).toHaveCount(0)
    await page.goto('/#/set/optimization')
    await expect(page).toHaveURL(/#\/set\/permission$/)
    await expect(page.getByRole('heading', { name: '权限配置' })).toBeVisible()
  })

  test('首页显示实际状态，模型配置按地址、密钥和模型依次操作', async ({ page }) => {
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('/#/chat/index')
    await expect(page.getByRole('heading', { name: '用一句话，找到数据中的答案。' })).toBeVisible()
    await expect.poll(() => page.getByRole('menuitem', { name: '智能问数', exact: true }).evaluate(el => getComputedStyle(el).display)).toBe('flex')
    await expect(page.locator('.readiness')).not.toContainText('读取配置中')
    const card = page.locator('.setup-grid .motion-card').first()
    await expect.poll(() => card.evaluate(el => el.getAnimations().every(a => a.playState === 'finished'))).toBe(true)
    await card.hover({ position: { x: 20, y: 20 } })
    await expect(card).toHaveAttribute('data-spotlight-active', 'true')
    await expect.poll(() => card.evaluate(el => getComputedStyle(el).transform)).not.toBe('none')
    await page.screenshot({ path: 'output/sql-workbench-hover-desktop.png', animations: 'disabled' })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.mouse.move(1, 1)
    await card.hover()
    await expect.poll(() => card.evaluate(el => getComputedStyle(el).transform)).toBe('none')
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.getByRole('button', { name: '配置模型', exact: false }).click()
    await expect(page.getByRole('heading', { name: '把模型接入变成三分钟的配置' })).toBeVisible()
    await page.route('**/api/v1/system/aimodel/models', route => route.fulfill({ json: { code: 0, data: { models: ['model-a', 'model-b'] }, msg: '' } }))
    await page.getByRole('button', { name: '添加模型', exact: true }).first().click()
    const form = page.locator('.model-form')
    const inputs = form.locator('.ed-input__inner')
    await inputs.nth(0).fill('https://models.example.test/v1')
    await inputs.nth(1).fill('test-key')
    await page.getByRole('button', { name: '获取模型', exact: true }).click()
    await expect(form.getByRole('status')).toContainText('2')
    await expect(form.locator('input').last()).toHaveValue('model-a')
    await inputs.nth(0).fill('https://another.example.test/v1')
    await expect(inputs.nth(1)).toHaveValue('')
    expect(errors).toEqual([])
  })

})
