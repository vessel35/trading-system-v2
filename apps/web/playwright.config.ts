import { defineConfig, devices } from "@playwright/test";

// 로컬/opt-in 전용: 개발 PostgreSQL과 저장소 var/evidence가 모두 필요하다.
// 기본 CI에는 포함하지 않으며, 준비된 실 스택에서만 `npm run e2e`로 실행한다.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      name: "web-api",
      command:
        "../../.venv/bin/python -m uvicorn web_api.main:app --host 127.0.0.1 --port 8000",
      cwd: "../../services/web-api",
      url: "http://127.0.0.1:8000/openapi.json",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      name: "vite",
      command: "npm run dev",
      cwd: ".",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
