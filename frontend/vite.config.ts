import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served from https://<user>.github.io/Player-Prop-Finder/ (a GitHub Pages
// project site), so all asset URLs need that path prefix. GitHub Pages
// paths are case-sensitive, so this must match the repo name's casing
// exactly -- a lowercase mismatch here 404s every JS/CSS asset and leaves
// the page blank.
export default defineConfig({
  base: "/Player-Prop-Finder/",
  plugins: [react()],
});
