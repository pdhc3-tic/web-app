import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Testes de componente (Vitest + Testing Library, em jsdom).
 * Ficam ao lado do componente como `*.test.tsx`; os E2E continuam no
 * Playwright, em `e2e/`, fora daqui.
 */
export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    include: ["app/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
    restoreMocks: true,
  },
});
