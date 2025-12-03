/**
 * Configuration Nuxt.js pour Telia Assistant
 * 
 * Ce fichier configure l'application Nuxt avec les modules nécessaires,
 * les variables d'environnement et les paramètres de l'application.
 */

export default defineNuxtConfig({
  // Activation des outils de développement
  devtools: { enabled: true },

  // Modules Nuxt utilisés dans l'application
  modules: [
    '@pinia/nuxt', // Gestion d'état avec Pinia
  ],

  // Configuration des variables d'environnement runtime
  runtimeConfig: {
    // Clé API Gemini (côté serveur uniquement pour la sécurité)
    geminiApiKey: process.env.GEMINI_API_KEY || 'AIzaSyBg2Nou49bo8FDMkpXfIAmC-6K7AHwzZbc',
    
    // Variables publiques accessibles côté client
    public: {
      // URL de base de l'API backend
      apiBaseUrl: process.env.API_BASE_URL || 'http://localhost:8000',
      // Nom de l'application
      appName: 'Telia Assistant',
    }
  },

  // Configuration de l'application
  app: {
    // Métadonnées de la page HTML
    head: {
      title: 'Telia Assistant - Glotelho',
      charset: 'utf-8',
      viewport: 'width=device-width, initial-scale=1',
      meta: [
        { name: 'description', content: 'Assistant intelligent pour vos achats sur Glotelho' },
        { name: 'theme-color', content: '#E53935' }
      ],
      // Polices Glotelho (Poppins + Open Sans)
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600&family=Poppins:wght@500;600;700&display=swap' },
        { rel: 'icon', type: 'image/svg+xml', href: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="%23FF6600"/><rect x="25" y="35" width="50" height="35" rx="5" fill="white"/><circle cx="38" cy="50" r="6" fill="%23FF6600"/><circle cx="62" cy="50" r="6" fill="%23FF6600"/></svg>' }
      ]
    }
  },

  // Configuration CSS globale
  css: [
    '~/assets/css/main.css'
  ],

  // Mode de compatibilité
  compatibilityDate: '2024-11-01'
})
