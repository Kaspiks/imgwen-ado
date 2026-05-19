import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // run-edit chains several DashScope calls; default proxy timeouts are ~2m
        timeout: 600_000,
        proxyTimeout: 600_000,
      },
    },
  },
});
