import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Vercel services expose the API on this deployment's public /api route.
  // Runtime-only internal bindings must never be baked into browser assets.
  define: process.env.VERCEL === "1"
    ? { "import.meta.env.VITE_API_BASE_URL": JSON.stringify("/api") }
    : {},

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom"],
          map: ["leaflet", "react-leaflet"],
          icons: ["lucide-react"],
        },
      },
    },
  },
});
