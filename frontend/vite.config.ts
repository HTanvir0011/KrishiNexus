import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const BACKEND = "http://localhost:8000";
const BACKEND_PREFIXES = ["/mcp", "/rag", "/edge", "/agents", "/automation", "/guardrails", "/optimization", "/prompts", "/evals", "/health"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      ...Object.fromEntries(BACKEND_PREFIXES.map((prefix) => [prefix, { target: BACKEND, changeOrigin: true }])),
      "/api": { target: BACKEND, changeOrigin: true, rewrite: (path: string) => path.replace(/^\/api/, "") },
      "/ws": { target: BACKEND.replace("http", "ws"), ws: true },
    },
  },
});
