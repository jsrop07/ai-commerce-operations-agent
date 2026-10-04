import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    css: true,
    env: {
      VITE_USE_REAL_BACKEND: "false",
    },
  },
});
