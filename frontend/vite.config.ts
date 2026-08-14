import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the FastAPI backend so the browser only ever
// talks to the Vite origin. The FAL_KEY stays on the backend; the frontend
// never sees it. SSE (text/event-stream) is proxied too.
// The backend origin can be overridden with VITE_BACKEND_URL (defaults to
// http://127.0.0.1:8000) so the API port can be changed without code edits.
const backendUrl = process.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
});
