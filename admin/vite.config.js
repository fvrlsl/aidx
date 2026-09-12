import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/admin": { target: "http://127.0.0.1:8000", bypass: (req) => (req.headers.accept?.includes("text/html") ? "/index.html" : undefined) },
      "/media": "http://127.0.0.1:8000",
    },
  },
});
