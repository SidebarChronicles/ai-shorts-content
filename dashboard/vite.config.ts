import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // Subdir under docs/ so the build doesn't collide with existing markdown playbooks.
  // Pages source is main /docs; dashboard URL is …github.io/ai-shorts-content/dashboard/.
  base: "/ai-shorts-content/dashboard/",
  plugins: [react()],
  build: {
    outDir: "../docs/dashboard",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
  },
});
