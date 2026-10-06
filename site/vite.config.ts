import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Strict CSP for the built site only: the dev server injects inline scripts for hot reload (spec 016 Security).
const csp: Plugin = {
  name: "csp",
  apply: "build",
  transformIndexHtml: (html) =>
    html.replace(
      "<head>",
      `<head>\n    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self'; connect-src https://api.github.com; base-uri 'self'; form-action 'none'" />`,
    ),
};

export default defineConfig({
  // "/" for hosts that serve the site at the root (Vercel, a custom domain); the Pages workflow sets SITE_BASE=/Galliani/.
  base: process.env.SITE_BASE ?? "/",
  plugins: [react(), tailwindcss(), csp],
  build: {
    rollupOptions: {
      input: { index: fileURLToPath(new URL("index.html", import.meta.url)), privacy: fileURLToPath(new URL("privacy.html", import.meta.url)) },
    },
  },
});
