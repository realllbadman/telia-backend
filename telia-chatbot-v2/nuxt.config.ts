import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  devtools: { enabled: true },
  vite: {
    optimizeDeps: {
      exclude: ['nuxt', '@nuxt/devtools']
    }
  },
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.API_BASE_URL || 'http://127.0.0.1:8000',
      apiToken: process.env.API_TOKEN || ''
    }
  }
})
