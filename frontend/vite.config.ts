import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@shared": path.resolve(__dirname, "../shared"),
    },
  },
  server: {
    port: 5173,
    // Module 10/11: allow this dev server to be reached through a
    // Cloudflare quick tunnel for external browser verification. Vite
    // blocks unrecognized Host headers by default; the leading-dot form
    // allows any trycloudflare.com subdomain, since quick-tunnel URLs are
    // randomly generated per run.
    allowedHosts: [".trycloudflare.com"],
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
