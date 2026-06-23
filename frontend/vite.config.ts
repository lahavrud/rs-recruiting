/// <reference types="vitest/config" />
import { sentryVitePlugin } from "@sentry/vite-plugin";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

import path from "path";

/** Injects the Google Tag Manager <head> snippet + <noscript> fallback into
 *  index.html at build time. Conditional on VITE_GTM_ID so dev builds and
 *  feature branches don't pollute the prod GTM container with junk events.
 *  A GTM Consent Mode v2 block is injected before the GTM snippet so that
 *  analytics cookies are withheld until the user grants consent. */
function gtmPlugin(containerId: string): Plugin {
  const consentInit = `<script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){window.dataLayer.push(arguments);}
    (function(){
      var c = null;
      try { c = JSON.parse(localStorage.getItem('cookie_consent')); } catch (e) {}
      var granted = c && c.analytics === true;
      var d = {
        analytics_storage: granted ? 'granted' : 'denied',
        ad_storage: 'denied',
        ad_user_data: 'denied',
        ad_personalization: 'denied'
      };
      if (!c) { d.wait_for_update = 2000; }
      gtag('consent', 'default', d);
    })();
  </script>`;
  const headSnippet = `${consentInit}
    <!-- Google Tag Manager -->
    <script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','${containerId}');</script>
    <!-- End Google Tag Manager -->`;
  const bodySnippet = `<!-- Google Tag Manager (noscript) -->
    <noscript><iframe src="https://www.googletagmanager.com/ns.html?id=${containerId}"
    height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
    <!-- End Google Tag Manager (noscript) -->`;
  return {
    name: "gtm-inject",
    transformIndexHtml: {
      order: "pre",
      handler(html) {
        return html
          .replace("<head>", `<head>\n    ${headSnippet}`)
          .replace("<body>", `<body>\n    ${bodySnippet}`);
      },
    },
  };
}

export default defineConfig({
  build: {
    sourcemap: "hidden",
    // Cap-warning at 600KB after the split; the remaining "vendor" bundle
    // bumps near it but doesn't really exceed it once gzipped.
    chunkSizeWarningLimit: 600,
    rolldownOptions: {
      output: {
        // Split rarely-changing third-party code into separate chunks so the
        // browser cache survives our app deploys. Each visitor downloads
        // React/Router/etc. once and reuses it across releases.
        manualChunks: (id: string) => {
          if (!id.includes("node_modules")) return undefined;
          if (/[\\/]@sentry[\\/]/.test(id)) return "vendor-sentry";
          if (/[\\/]@radix-ui[\\/]/.test(id)) return "vendor-radix";
          if (/[\\/](i18next|react-i18next)[\\/]/.test(id)) return "vendor-i18n";
          if (/[\\/](react|react-dom|react-router|react-router-dom|react-helmet-async|scheduler)[\\/]/.test(id)) {
            return "vendor-react";
          }
          return undefined;
        },
      },
    },
  },
  plugins: [
    react(),
    tailwindcss(),
    ...(process.env.VITE_GTM_ID ? [gtmPlugin(process.env.VITE_GTM_ID)] : []),
    ...(process.env.SENTRY_AUTH_TOKEN
      ? [
          sentryVitePlugin({
            org: "rs-recruiting",
            project: "rs-recruiting-frontend",
            authToken: process.env.SENTRY_AUTH_TOKEN,
            release: { name: process.env.VITE_RELEASE },
            sourcemaps: { filesToDeleteAfterUpload: ["./dist/**/*.map"] },
          }),
        ]
      : []),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/auth": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/robots.txt": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/sitemap.xml": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
