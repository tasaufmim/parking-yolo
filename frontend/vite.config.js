import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/upload": "http://localhost:8000",
      "/connect_rtsp": "http://localhost:8000",
      "/disconnect": "http://localhost:8000",
      "/video_feed": "http://localhost:8000",
      "/snapshot": "http://localhost:8000",
      "/resolution": "http://localhost:8000",
      "/roi": "http://localhost:8000",
      "/status": "http://localhost:8000",
      "/history": "http://localhost:8000",
    },
  },
  build: {
    outDir: "../static",
    emptyOutDir: true,
  },
});
