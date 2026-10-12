// @ts-check
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "astro/config"
import react from "@astrojs/react"

// Static build served by Vercel's CDN; /api/* goes to the Python Function (vercel.json).
// security.csp adds a CSP <meta> with hashes for every inline script and style Astro emits,
// so the page needs no 'unsafe-inline'.
export default defineConfig({
  output: "static",
  integrations: [react()],
  security: {
    csp: {
      directives: [
        "default-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
      ],
    },
  },
  vite: {
    plugins: [tailwindcss()],
    server: { proxy: { "/api": "http://127.0.0.1:8765" } },
  },
})
