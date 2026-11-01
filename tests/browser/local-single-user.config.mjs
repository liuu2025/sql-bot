import { defineConfig } from '@playwright/test'
import base from './playwright.config.mjs'

export default defineConfig({
  ...base,
  webServer: undefined,
  projects: [{
    name: 'local-single-user',
    testMatch: 'local-single-user.spec.mjs',
    use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:7200', storageState: { cookies: [], origins: [] } }
  }],
  // Local session responses contain credentials: keep traces disabled.
  use: { ...base.use, trace: 'off', screenshot: 'only-on-failure' },
  outputDir: 'output/local-single-user-results'
})
