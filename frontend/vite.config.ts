import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served from https://<user>.github.io/player-prop-finder/ (a GitHub Pages
// project site), so all asset URLs need that path prefix.
export default defineConfig({
  base: "/player-prop-finder/",
  plugins: [react()],
});
