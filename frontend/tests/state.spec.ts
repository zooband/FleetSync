import { test, expect, type Locator, type Page } from '@playwright/test'

function uniqueName(prefix: string): string {
    return `${prefix}-${Date.now()}`
}

async function extractFirstMatch(locator: Locator, re: RegExp): Promise<string> {
    const text = (await locator.textContent()) ?? ''
    const m = text.match(re)
    expect(m, `未能从文本中匹配 ${re}：${text}`).toBeTruthy()
    return (m as RegExpMatchArray)[1]
}

function todayISO(): string {
    return new Date().toLocaleDateString('sv-SE')
}

async function navBySideButton(page: Page, name: string) {
    await page.getByRole('button', { name }).locator('a').click()
}

async function fillFieldInDialog(dialog: Locator, label: string, value: string | number) {
    const container = dialog.locator('label', { hasText: label }).first().locator('..')
    await container.locator('input').first().fill(String(value))
}

async function selectOptionInDialog(dialog: Locator, label: string, optionName: string) {
    const container = dialog.locator('label', { hasText: label }).first().locator('..')
    await container.getByRole('combobox').click()
    await dialog.page().getByRole('option', { name: optionName }).click()
}

test('状态转移（去硬编码/补全输入/减少冗余）', async ({ page }) => {
    test.setTimeout(120_000)
    const base = 'http://localhost:5173/#'

    const centerName = uniqueName('华南配送中心')
    const fleetNameA = uniqueName('广州配送车队')
    const fleetNameB = uniqueName('广惠快速配送车队')

    const managerNameA = '徐广'
    const managerContactA = '15973426512'
    const managerNameB = '广辉'
    const managerContactB = '16495782354'

    const vehicleA = `粤A${Math.floor(10000 + Math.random() * 89999)}`
    const vehicleB = `桂A${Math.floor(1000 + Math.random() * 8999)}挂`
    const vehicleC = `沪B${Math.floor(10000 + Math.random() * 89999)}`
    const vehicleD = `贵F${Math.floor(10000 + Math.random() * 89999)}`

    const driver1 = { name: '斯基', contact: '13894642157', license: 'A2' }
    const driver2 = { name: '刘鑫', contact: 'liu@gmail.com', license: 'B2' }

    // 订单（验证：待处理 -> 装货中 -> 运输中 -> 已完成；另测取消）
    const orderMain = { origin: '广州天河', dest: '广州增城', weight: 4000, volume: 10000 }
    const orderCancel = { origin: '广州', dest: '佛山', weight: 10, volume: 50 }

    // 登录
    await page.goto(`${base}/login`)
    await page.getByRole('textbox', { name: 'admin 或 工号' }).fill('admin')
    await page.getByRole('textbox', { name: 'admin 或 工号' }).press('Enter')

    // 创建配送中心
    await page.getByRole('button', { name: '添加' }).click()
    await page.getByRole('textbox').fill(centerName)
    await page.getByRole('button', { name: '确认' }).click()
    await expect(page.getByRole('main')).toContainText(centerName)

    const centerCard = page.getByRole('button', { name: new RegExp(centerName) })
    const centerId = await extractFirstMatch(centerCard, /配送中心ID：\s*(\d+)/)

    // 进入配送中心详情页
    await centerCard.click()
    await expect(page.getByRole('heading', { name: '配送中心详情' })).toBeVisible()
    await expect(
        page.getByText('配送中心ID', { exact: true }).locator('..').locator('span').nth(1),
    ).toHaveText(centerId)
    await expect(
        page.getByText('配送中心名', { exact: true }).locator('..').locator('span').nth(1),
    ).toHaveText(centerName)

    // 在配送中心下创建两个车队
    await page.getByRole('button', { name: '添加' }).click()
    await page.getByRole('textbox').nth(0).fill(fleetNameA)
    await page.getByRole('textbox').nth(1).fill(managerNameA)
    await page.getByRole('textbox').nth(2).fill(managerContactA)
    await page.getByRole('button', { name: '确认' }).click()

    const fleetCardA = page.getByRole('button', { name: new RegExp(fleetNameA) })
    const fleetIdA = await extractFirstMatch(fleetCardA, /车队ID：\s*(\d+)/)

    await page.getByRole('button', { name: '添加' }).click()
    await page.getByRole('textbox').nth(0).fill(fleetNameB)
    await page.getByRole('textbox').nth(1).fill(managerNameB)
    await page.getByRole('textbox').nth(2).fill(managerContactB)
    await page.getByRole('button', { name: '确认' }).click()

    const fleetCardB = page.getByRole('button', { name: new RegExp(fleetNameB) })
    const fleetIdB = await extractFirstMatch(fleetCardB, /车队ID：\s*(\d+)/)
    expect(fleetIdA).not.toBe(fleetIdB)

    // 进入车队A：添加车辆/司机，验证初始状态
    await fleetCardA.click()
    await expect(page.getByRole('heading', { name: '车队详情' })).toBeVisible()
    await expect(
        page.getByText('车队ID', { exact: true }).locator('..').locator('span').nth(1),
    ).toHaveText(fleetIdA)
    await expect(
        page.getByText('车队名', { exact: true }).locator('..').locator('span').nth(1),
    ).toHaveText(fleetNameA)
    await expect(
        page.getByText('调度主管名', { exact: true }).locator('..').locator('span').nth(1),
    ).toContainText(managerNameA)
    await expect(
        page.getByText('调度主管联系方式', { exact: true }).locator('..').locator('span').nth(1),
    ).toHaveText(managerContactA)

    // 车队A添加车辆 vehicleA / vehicleB
    await page.getByRole('button', { name: '添加' }).first().click()
    const vDialog1 = page.getByRole('dialog', { name: '新增' })
    await fillFieldInDialog(vDialog1, '车牌号', vehicleA)
    await fillFieldInDialog(vDialog1, '载重上限', 8000)
    await fillFieldInDialog(vDialog1, '容积上限', 9000)
    await vDialog1.getByRole('button', { name: '确认' }).click()

    const vehicleCardA = page.getByRole('button', { name: new RegExp(vehicleA) })
    await expect(vehicleCardA).toContainText('司机')
    await expect(vehicleCardA).toContainText('载重上限：8000')
    await expect(vehicleCardA).toContainText('容积上限：9000')
    await expect(vehicleCardA).toContainText('剩余载重：8000')
    await expect(vehicleCardA).toContainText('剩余容积：9000')
    await expect(vehicleCardA).toContainText('状态：空闲')

    await page.getByRole('button', { name: '添加' }).first().click()
    const vDialog2 = page.getByRole('dialog', { name: '新增' })
    await fillFieldInDialog(vDialog2, '车牌号', vehicleB)
    await fillFieldInDialog(vDialog2, '载重上限', 100000)
    await fillFieldInDialog(vDialog2, '容积上限', 500000)
    await vDialog2.getByRole('button', { name: '确认' }).click()

    const vehicleCardB = page.getByRole('button', { name: new RegExp(vehicleB) })
    await expect(vehicleCardB).toContainText('司机')
    await expect(vehicleCardB).toContainText('载重上限：100000')
    await expect(vehicleCardB).toContainText('容积上限：500000')
    await expect(vehicleCardB).toContainText('剩余载重：100000')
    await expect(vehicleCardB).toContainText('剩余容积：500000')
    await expect(vehicleCardB).toContainText('状态：空闲')

    // 车队A添加两位司机
    await page.getByRole('button', { name: '添加' }).nth(1).click()
    const dDialog1 = page.getByRole('dialog', { name: '新增' })
    await fillFieldInDialog(dDialog1, '姓名', driver1.name)
    await fillFieldInDialog(dDialog1, '联系方式', driver1.contact)
    await dDialog1.getByRole('button', { name: '确认' }).click()

    await page.getByRole('button', { name: '添加' }).nth(1).click()
    const dDialog2 = page.getByRole('dialog', { name: '新增' })
    await fillFieldInDialog(dDialog2, '姓名', driver2.name)
    await fillFieldInDialog(dDialog2, '联系方式', driver2.contact)
    await selectOptionInDialog(dDialog2, '驾照等级', driver2.license)
    await dDialog2.getByRole('button', { name: '确认' }).click()

    const driverCard1 = page.getByRole('button', { name: new RegExp(driver1.name) })
    const driverId1 = await extractFirstMatch(driverCard1, /工号：\s*(D\d+)/)
    await expect(driverCard1).toContainText('状态：空闲')

    // 车队B：添加车辆/司机，切换维护模式，验证配送中心“不可用车辆”
    await page.goto(`${base}/fleet/${fleetIdB}`)
    await expect(page.getByRole('heading', { name: '车队详情' })).toBeVisible()

    await page.getByRole('button', { name: '添加' }).first().click()
    const vDialog3 = page.getByRole('dialog', { name: '新增' })
    await fillFieldInDialog(vDialog3, '车牌号', vehicleC)
    await fillFieldInDialog(vDialog3, '载重上限', 4000)
    await fillFieldInDialog(vDialog3, '容积上限', 8000)
    await vDialog3.getByRole('button', { name: '确认' }).click()

    await page.getByRole('button', { name: '添加' }).first().click()
    const vDialog4 = page.getByRole('dialog', { name: '新增' })
    await fillFieldInDialog(vDialog4, '车牌号', vehicleD)
    await fillFieldInDialog(vDialog4, '载重上限', 100)
    await fillFieldInDialog(vDialog4, '容积上限', 300)
    await vDialog4.getByRole('button', { name: '确认' }).click()

    const vehicleCardD = page.getByRole('button', { name: new RegExp(vehicleD) })
    await expect(vehicleCardD).toContainText('状态：空闲')

    // 维护模式：空闲 -> 维修中
    await vehicleCardD.getByRole('button', { name: '维护模式' }).click()
    await expect(vehicleCardD).toContainText('状态：维修中')

    // 回到配送中心资源查询：应能在“不可用车辆”中看到 vehicleD
    await page.goto(`${base}/distribution/${centerId}`)
    await expect(page.getByRole('heading', { name: '配送中心详情' })).toBeVisible()
    await page.getByRole('tab', { name: '不可用车辆' }).click()
    await expect(page.getByLabel('不可用车辆')).toContainText(vehicleD)

    // 运单：待处理 -> 装货中，并验证车辆剩余载重/容积变化
    await navBySideButton(page, '运单管理')
    await expect(page.getByRole('heading', { name: '订单管理' })).toBeVisible()

    // 创建一个可取消订单
    await page.getByRole('button', { name: '添加' }).click()
    const oDialog1 = page.getByRole('dialog', { name: '新增' })
    await fillFieldInDialog(oDialog1, '始发地', orderCancel.origin)
    await fillFieldInDialog(oDialog1, '目的地', orderCancel.dest)
    await fillFieldInDialog(oDialog1, '货物重量', orderCancel.weight)
    await fillFieldInDialog(oDialog1, '货物体积', orderCancel.volume)
    await oDialog1.getByRole('button', { name: '确认' }).click()

    // 创建主流程订单
    await page.getByRole('button', { name: '添加' }).click()
    const oDialog2 = page.getByRole('dialog', { name: '新增' })
    await fillFieldInDialog(oDialog2, '始发地', orderMain.origin)
    await fillFieldInDialog(oDialog2, '目的地', orderMain.dest)
    await fillFieldInDialog(oDialog2, '货物重量', orderMain.weight)
    await fillFieldInDialog(oDialog2, '货物体积', orderMain.volume)
    await oDialog2.getByRole('button', { name: '确认' }).click()

    // 取消订单：待处理 -> 已取消
    const cancelOrderCard = page.getByRole('button', {
        name: new RegExp(`${orderCancel.origin}.*${orderCancel.dest}`),
    })
    await cancelOrderCard.getByRole('button', { name: '取消订单' }).click()
    await page.getByRole('tab', { name: '已取消' }).click()
    await expect(page.getByLabel('已取消')).toContainText(orderCancel.dest)
    await page.getByRole('tab', { name: '待处理' }).click()

    // 分配车辆：待处理 -> 装货中
    const mainOrderCard = page.getByRole('button', {
        name: new RegExp(`${orderMain.origin}.*${orderMain.dest}`),
    })
    const mainOrderId = await extractFirstMatch(mainOrderCard, /^(\d+)/)
    await mainOrderCard.getByRole('button', { name: '分配车辆' }).click()
    const assignDialog = page.getByRole('dialog', { name: '分配车辆' })
    await assignDialog.getByRole('combobox').click()
    await page.getByRole('option', { name: vehicleB }).click()
    await assignDialog.getByRole('button', { name: '确认' }).click()

    await page.getByRole('tab', { name: '装货中' }).click()
    await expect(page.getByLabel('装货中')).toContainText(`${mainOrderId}`)
    await expect(page.getByLabel('装货中')).toContainText(vehicleB)
    await expect(page.getByLabel('装货中')).toContainText('状态：装货中')

    // 回到配送中心资源表，vehicleB 的剩余应减少
    await page.goto(`${base}/distribution/${centerId}`)
    await expect(page.getByRole('heading', { name: '配送中心详情' })).toBeVisible()
    await expect(page.getByRole('main')).toContainText(vehicleB)
    await expect(page.getByRole('main')).toContainText('96000')
    await expect(page.getByRole('main')).toContainText('490000')

    // 车队A：分配司机、开始发车、确认送达（状态链路）
    await page.goto(`${base}/fleet/${fleetIdA}`)
    const vehicleCardB2 = page.getByRole('button', { name: new RegExp(vehicleB) })
    await expect(vehicleCardB2).toContainText('状态：装货中')

    // 分配司机
    await vehicleCardB2.getByRole('button', { name: '分配司机' }).click()
    const assignDriverDialog = page.getByRole('dialog', { name: '分配司机' })
    await assignDriverDialog.getByRole('combobox').click()
    await page.getByRole('option', { name: driver1.name }).click()
    await assignDriverDialog.getByRole('button', { name: '确认' }).click()
    await expect(vehicleCardB2).toContainText(`司机：${driver1.name}`)
    await expect(page.getByRole('main')).toContainText(`${driver1.name}`)
    await expect(page.getByRole('main')).toContainText(driverId1)

    // 装货中 -> 运输中
    await vehicleCardB2.getByRole('button', { name: '开始发车', exact: true }).click()
    await expect(vehicleCardB2).toContainText('状态：运输中')

    // 运输中 -> 已完成/车辆回空闲
    await vehicleCardB2.getByRole('button', { name: '确认送达', exact: true }).click()
    await expect(vehicleCardB2).toContainText('状态：空闲')
    await expect(vehicleCardB2).toContainText('剩余载重：100000')
    await expect(vehicleCardB2).toContainText('剩余容积：500000')

    // 运单应进入“已完成”
    await navBySideButton(page, '运单管理')
    await page.getByRole('tab', { name: '已完成' }).click()
    await expect(page.getByLabel('已完成')).toContainText(`${mainOrderId}`)
    await expect(page.getByLabel('已完成')).toContainText('状态：已完成')

    // 异常事件：新增（未处理）-> 行内编辑为（已处理），并回写车辆状态
    await navBySideButton(page, '异常事件')
    await expect(page.getByRole('heading', { name: '异常事件' })).toBeVisible()

    await page.getByRole('button', { name: '添加记录' }).click()
    const iDialog = page.getByRole('dialog', { name: /^添加/ })
    await selectOptionInDialog(iDialog, '关联司机', driver1.name)
    await selectOptionInDialog(iDialog, '车辆', vehicleB)
    await fillFieldInDialog(iDialog, '时间', todayISO())
    await selectOptionInDialog(iDialog, '异常类型', '空闲时异常')
    await fillFieldInDialog(iDialog, '异常描述', '超速报警')
    await fillFieldInDialog(iDialog, '罚款金额', 400)
    await selectOptionInDialog(iDialog, '异常处理状态', '未处理')
    await iDialog.getByRole('button', { name: '确认' }).click()

    const incidentRow = page
        .locator('table tbody tr')
        .filter({ hasText: driverId1 })
        .filter({ hasText: vehicleB })
        .first()
    await expect(incidentRow).toContainText(todayISO())
    await expect(incidentRow).toContainText('未处理')
    const incidentId = await extractFirstMatch(incidentRow, /^(\d+)/)

    // 行内编辑：未处理 -> 已处理
    await incidentRow.getByRole('button', { name: 'Row Edit' }).click()
    await incidentRow.getByRole('combobox').click()
    await page.getByText('已处理', { exact: true }).click()
    await incidentRow.getByRole('button', { name: 'Save Edit' }).click()
    await expect(incidentRow).toContainText('已处理')

    // 回到车队A：车辆应显示“异常”状态（后端/前端如果有该联动）
    await page.goto(`${base}/fleet/${fleetIdA}`)
    await expect(page.getByRole('main')).toContainText(vehicleB)
    await expect(page.getByRole('main')).toContainText(`异常事件总数`)

    // 最终断言：异常记录存在、处理状态正确
    await navBySideButton(page, '异常事件')
    await expect(page.getByRole('main')).toContainText(incidentId)
    await expect(page.getByRole('main')).toContainText('已处理')
})
