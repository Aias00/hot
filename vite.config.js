import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = process.env.HOT_BACKEND_ORIGIN || "http://127.0.0.1:18000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backendTarget,
      "/healthz": backendTarget,
      "/runs": backendTarget,
      "/analytics": backendTarget,
      "/notifications": backendTarget,
      "/twitter": backendTarget,
      "/feed-engage": backendTarget,
      "/author-alpha": backendTarget,
    },
  },
  preview: {
    proxy: {
      "/api": backendTarget,
      "/healthz": backendTarget,
      "/runs": backendTarget,
      "/analytics": backendTarget,
      "/notifications": backendTarget,
      "/twitter": backendTarget,
      "/feed-engage": backendTarget,
      "/author-alpha": backendTarget,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.js",
    include: ["src/**/*.{test,spec}.{js,jsx}"],
    exclude: ["src/lib/feed.test.js"],
  },
});
