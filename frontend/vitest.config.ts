import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    environmentOptions: {
      jsdom: { url: "http://localhost" },
    },
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    fileParallelism: false,
    maxWorkers: 1,
  },
});
