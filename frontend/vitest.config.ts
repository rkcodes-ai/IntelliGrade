import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@shared": path.resolve(__dirname, "../shared"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/tests/setup.ts"],
    css: true,
    exclude: ["**/node_modules/**", "**/dist/**", "src/tests/e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      exclude: [
        "node_modules/",
        "dist/",
        "src/tests/",
        "**/*.d.ts",
        "**/*.config.*",
        // Bootstrap/entrypoint code — no business logic to unit test, same
        // rationale as the backend excluding app/tasks/celery_app.py.
        // App.tsx additionally renders RouterProvider against a real
        // createBrowserRouter, which hits the same jsdom AbortSignal
        // incompatibility as createMemoryRouter (see routes/guards tests).
        "src/main.tsx",
        "src/App.tsx",
        // Pure type declarations, no runtime logic.
        "src/types/**",
      ],
    },
  },
});
