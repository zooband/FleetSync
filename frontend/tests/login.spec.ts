import { test, expect } from '@playwright/test'

test('test', async ({ page }) => {
    await page.goto('http://localhost:5173/#/login')
    await page.getByRole('textbox', { name: 'admin 或 工号' }).click()
    await page.getByRole('textbox', { name: 'admin 或 工号' }).fill('1')
    await page.getByRole('button', { name: '登录' }).click()
    await expect(page.getByRole('main')).toContainText('工号不存在，请先用 admin 创建人员')
    await page.getByRole('textbox', { name: 'admin 或 工号' }).click()
    await page.getByRole('textbox', { name: 'admin 或 工号' }).fill('2')
    await page.getByRole('button', { name: '登录' }).click()
    await expect(page.getByRole('main')).toContainText('工号不存在，请先用 admin 创建人员')
    await page.getByRole('textbox', { name: 'admin 或 工号' }).click()
    await page.getByRole('textbox', { name: 'admin 或 工号' }).fill('admin')
    await page.getByRole('button', { name: '登录' }).click()
    await page.getByRole('button', { name: '人员管理' }).locator('a').click()
    await page.getByRole('button', { name: '添加' }).click()
    await page.getByRole('textbox').first().click()
    await page.getByRole('textbox').first().fill('')
    await page.getByRole('button', { name: '确认' }).click()
    await expect(page.getByRole('alert')).toContainText('请填写必填项：姓名')
    await page.getByRole('alert').getByRole('button', { name: 'Close' }).click()
    await page.getByRole('textbox').first().click()
    await page.getByRole('textbox').first().fill('李仁杰')
    await page.getByRole('button', { name: '确认' }).click()
    await expect(page.getByLabel('全部人员')).toContainText('李仁杰工号：1联系方式：职务：普通员工')
    await page.getByRole('button').filter({ hasText: /^$/ }).first().click()
    await page.getByRole('textbox').first().click()
    await page.getByRole('textbox').first().fill('李佳和')
    await page.getByRole('textbox').nth(1).click()
    await page.getByRole('textbox').nth(1).fill('19815010263')
    await page.getByRole('button', { name: '确认' }).click()
    await expect(page.getByLabel('全部人员')).toContainText(
        '李佳和工号：1联系方式：19815010263职务：普通员工',
    )
    await page.getByRole('button', { name: '添加' }).click()
    await page.getByRole('textbox').first().click()
    await page.getByRole('textbox').first().fill('郭贤青')
    await page.getByRole('textbox').nth(1).click()
    await page.getByRole('textbox').nth(1).fill('guo@gmail.com')
    await page.getByRole('button', { name: '确认' }).click()
    await expect(page.getByLabel('全部人员')).toContainText(
        '郭贤青工号：2联系方式：guo@gmail.com职务：普通员工',
    )
    await page.getByRole('button', { name: '添加' }).click()
    await page.getByRole('textbox').first().click()
    await page.getByRole('textbox').first().fill('Anastasia')
    await page.getByRole('button', { name: '确认' }).click()
    await expect(page.getByLabel('全部人员')).toContainText(
        'Anastasia工号：3联系方式：职务：普通员工',
    )
    await page.getByRole('tab', { name: '普通员工' }).click()
    await expect(page.getByRole('main')).toContainText(
        '共 3 条记录，当前显示 3 条刷新李佳和工号：1联系方式：19815010263职务：普通员工郭贤青工号：2联系方式：guo@gmail.com职务：普通员工Anastasia工号：3联系方式：职务：普通员工112',
    )
    await page.getByRole('tab', { name: '主管' }).click()
    await expect(page.getByLabel('主管')).toContainText('共 0 条记录，当前显示 0 条刷新')
    await page.getByRole('tab', { name: '司机' }).click()
    await expect(page.getByLabel('司机')).toContainText('共 0 条记录，当前显示 0 条刷新')
    await page.getByRole('button', { name: '添加' }).click()
    await page.locator('#pv_id_172').click()
    await page.getByRole('option', { name: '郭贤青' }).click()
    await page.getByRole('combobox', { name: 'A2' }).click()
    await page.getByRole('option', { name: 'B2' }).click()
    await page.getByRole('button', { name: '确认' }).click()
    await page.getByRole('button', { name: '刷新' }).click()
    await expect(page.getByLabel('司机')).toContainText('共 1 条记录，当前显示 1 条')
    await expect(page.getByLabel('司机')).toContainText(
        '郭贤青工号：2联系方式：guo@gmail.com职务：司机驾照等级：B2状态：空闲所属车队：驾驶车辆：',
    )
    await page.getByRole('tab', { name: '普通员工' }).click()
    await page.getByRole('button', { name: '刷新' }).click()
    await expect(page.getByLabel('普通员工')).toContainText(
        '共 2 条记录，当前显示 2 条刷新李佳和工号：1联系方式：19815010263职务：普通员工Anastasia工号：3联系方式：职务：普通员工112',
    )
})
