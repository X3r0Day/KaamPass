import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".", testMatch: "*.spec.ts", workers: 1, timeout: 120_000,
  expect: { timeout: 12_000 },
  use: {
    baseURL: "http://127.0.0.1:3000", viewport: { width: 390, height: 844 },
    launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined },
    // Test artifacts must not retain even emulator session cookies or verification codes.
    trace: "off", screenshot: "off", video: "off"
  }
});
