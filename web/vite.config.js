import { defineConfig } from "vite";
export default defineConfig({
  resolve: { dedupe: ["react", "react-dom"] },
  server: { proxy: { "/api": process.env.GYM_DEV_ORIGIN || "http://127.0.0.1:8787", "/app-config.json": process.env.GYM_DEV_ORIGIN || "http://127.0.0.1:8787" } },
  build: { target: "es2022" },
});
