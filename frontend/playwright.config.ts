import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * E2E do frontend.
 *
 * Os testes rodam contra a stack já de pé (`docker compose up`): Next em
 * :3000 e Django em :8000. Não há `webServer` aqui de propósito — subir um
 * segundo Next apontando para o mesmo banco só duplicaria o ambiente.
 *
 * `workers: 1` porque as specs compartilham o banco de demonstração; rodar em
 * paralelo faria um teste ver o estado que o outro está montando.
 */
const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  reporter: [["list"]],
  /**
   * Artefatos ficam FORA de `frontend/`: essa pasta é bind-mount do container
   * do Next em modo dev com WATCHPACK_POLLING, então qualquer arquivo escrito
   * aqui durante a execução dispara recompilação e recarrega a página no meio
   * do teste.
   */
  outputDir: path.resolve(__dirname, "..", ".playwright", "test-results"),
  use: {
    baseURL: BASE_URL,
    locale: "pt-BR",
    timezoneId: "America/Recife",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
  ],
});
