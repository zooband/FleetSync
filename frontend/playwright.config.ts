import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
    testDir: 'tests',
    timeout: 120_000,
    use: {
        headless: false,
        viewport: null,
        launchOptions: { args: ['--start-maximized'], slowMo: 500, },
        baseURL: 'http://localhost:5173',
        trace: 'on-first-retry',
    },
    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
