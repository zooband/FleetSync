# E2E 测试（Playwright）

本项目采用 Playwright 进行端到端测试与录制：
- Playwright 录制（codegen）可快速生成操作步骤
- Playwright 测试（UI/无头）可直接运行断言

## 运行前置
1. 启动后端 API（确保本地接口可用）
2. 启动前端：

```bash
npm run dev
```

默认访问地址为 http://localhost:5173

> 说明：已移除 Cypress 相关配置与依赖，统一使用 Playwright。

## Playwright（用于录制）
- 打开录制器（会启动一个带 UI 的浏览器，自动生成代码）：

```bash
npm run codegen:pw
```

- 在弹出的浏览器中完成你的操作，右侧会生成 Playwright 代码
- 录制完成后复制需要的步骤到 Cypress 用例，并做轻微改写（见下方对照）

运行 Playwright 测试：

```bash
# UI 模式
npm run e2e:open:pw

# CLI 无头模式
npm run e2e:run:pw
```

## Playwright常用对照
- 访问：Playwright: `await page.goto('/')`
- 点击按钮（可访问性角色+名称）：Playwright: `await page.getByRole('button', { name: '刷新' }).click()`
- 断言类名包含：Playwright: `await expect(locator).toHaveClass(/p-button-loading/)`
- 输入文本：Playwright: `await page.getByPlaceholder('用户名').fill('jack')`

> 小贴士：优先使用角色/名称等语义化选择器（按钮文本、`aria-label`、`placeholder` 等）。必要时可在元素上加上 `data-testid="xxx"` 并用 `cy.get('[data-testid="xxx"]')` 获取。

## 编写你的第一个用例
1. 用 Playwright 录制一段流程：
  - `npm run codegen:pw`
  - 在右侧复制关键步骤（访问页面、点击、输入等）
2. 在 `tests/` 下创建文件 `your-feature.spec.ts`，粘贴为 Playwright 语法并补充断言
3. 通过 `npm run e2e:open:pw` 或 `npm run e2e:run:pw` 运行

## 常见问题
- 看不到按钮的 loading 动画：已在实现中强制 `nextTick` 与最小显示时长（300ms）；如需更明显可延长至 500ms。
- 录制到的选择器过于脆弱：用 Testing Library 的语义选择器替换，或自行添加 `data-testid`。
- 端口不是 5173：请改 `playwright.config.ts` 的 `baseURL`。
