import { defineConfig, Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { VitePWA } from 'vite-plugin-pwa'
import { visualizer } from 'rollup-plugin-visualizer'

// Custom plugin to add CSP nonce placeholder for production builds
function cspNoncePlugin(): Plugin {
  return {
    name: 'csp-nonce-injection',
    enforce: 'post',
    transformIndexHtml(html) {
      // Add nonce placeholder to script tags
      html = html.replace(
        /<script(?![^>]*nonce)/g, 
        '<script nonce="{{CSP_NONCE}}"'
      )
      // Add nonce placeholder to style tags
      html = html.replace(
        /<style(?![^>]*nonce)/g,
        '<style nonce="{{CSP_NONCE}}"'
      )
      // Add nonce placeholder to link stylesheet tags
      html = html.replace(
        /<link([^>]*rel=["']stylesheet["'])(?![^>]*nonce)/g,
        '<link$1 nonce="{{CSP_NONCE}}"'
      )
      // Add nonce placeholder to link modulepreload tags (for Vite chunks)
      html = html.replace(
        /<link([^>]*rel=["']modulepreload["'])(?![^>]*nonce)/g,
        '<link$1 nonce="{{CSP_NONCE}}"'
      )
      return html
    }
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    cspNoncePlugin(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/api\./i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 300 }
            }
          }
        ]
      },
      manifest: {
        name: 'VFS-Bot Dashboard',
        short_name: 'VFS-Bot',
        description: 'Otomatik Randevu Takip Sistemi',
        theme_color: '#6366f1',
        background_color: '#0f172a',
        display: 'standalone',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    }),
    // Bundle analyzer for analyze mode
    mode === 'analyze' && visualizer({
      filename: './dist/stats.html',
      open: true,
      gzipSize: true,
      brotliSize: true,
    }),
  ].filter(Boolean),
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: path.resolve(__dirname, '../web/static/dist'),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['lucide-react', 'sonner'],
          'form-vendor': ['react-hook-form', 'zod', '@hookform/resolvers'],
          'chart-vendor': ['recharts'],
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
}));
