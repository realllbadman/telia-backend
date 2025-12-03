/**
 * Middleware d'authentification
 * 
 * Ce middleware protège les routes nécessitant une authentification.
 * Il vérifie si l'utilisateur est connecté et redirige vers la page
 * de connexion si ce n'est pas le cas.
 */

import { useAuthStore } from '~/stores/auth'

export default defineNuxtRouteMiddleware((to, from) => {
  // Exécuter uniquement côté client
  if (import.meta.server) return

  const authStore = useAuthStore()

  // Restaurer la session si nécessaire
  if (!authStore.token) {
    authStore.restoreSession()
  }

  // Rediriger vers login si non authentifié
  if (!authStore.isAuthenticated) {
    return navigateTo('/login')
  }
})



