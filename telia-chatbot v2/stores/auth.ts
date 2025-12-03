/**
 * Store Pinia pour la gestion de l'authentification
 * 
 * Ce store gère l'état de l'authentification utilisateur,
 * incluant la connexion, la déconnexion et la persistance du token.
 */

import { defineStore } from 'pinia'

// Interface pour les données utilisateur
export interface User {
  id: number
  email: string
  username: string
  full_name: string | null
  role: 'customer' | 'superadmin'
  is_active: boolean
  created_at: string
  updated_at: string | null
}

// Interface pour l'état du store
interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  error: string | null
}

export const useAuthStore = defineStore('auth', {
  /**
   * État initial du store d'authentification
   */
  state: (): AuthState => ({
    user: null,
    token: null,
    isLoading: false,
    error: null
  }),

  /**
   * Getters pour accéder aux données calculées
   */
  getters: {
    // Vérifie si l'utilisateur est authentifié
    isAuthenticated: (state): boolean => !!state.token && !!state.user,
    
    // Récupère le nom d'affichage de l'utilisateur
    displayName: (state): string => {
      if (state.user?.full_name) return state.user.full_name
      if (state.user?.username) return state.user.username
      return 'Utilisateur'
    },
    
    // Vérifie si l'utilisateur est superadmin
    isSuperAdmin: (state): boolean => state.user?.role === 'superadmin'
  },

  /**
   * Actions pour modifier l'état
   */
  actions: {
    /**
     * Connexion de l'utilisateur
     * 
     * @param credentials - Email/username et mot de passe
     * @returns Promise<boolean> - Succès de la connexion
     */
    async login(credentials: { email?: string; username?: string; password: string }): Promise<boolean> {
      const config = useRuntimeConfig()
      this.isLoading = true
      this.error = null

      try {
        // Appel à l'API de connexion
        const response = await $fetch<{
          access_token: string
          token_type: string
          user: User
        }>(`${config.public.apiBaseUrl}/auth/login`, {
          method: 'POST',
          body: credentials
        })

        // Mise à jour de l'état
        this.token = response.access_token
        this.user = response.user

        // Sauvegarde dans le localStorage pour la persistance
        if (import.meta.client) {
          localStorage.setItem('telia_token', response.access_token)
          localStorage.setItem('telia_user', JSON.stringify(response.user))
        }

        return true
      } catch (error: any) {
        // Gestion des erreurs
        this.error = error?.data?.detail || 'Erreur de connexion. Veuillez réessayer.'
        console.error('Erreur de connexion:', error)
        return false
      } finally {
        this.isLoading = false
      }
    },

    /**
     * Inscription d'un nouvel utilisateur
     * 
     * @param userData - Données de l'utilisateur à créer
     * @returns Promise<boolean> - Succès de l'inscription
     */
    async register(userData: {
      email: string
      username: string
      password: string
      full_name?: string
    }): Promise<boolean> {
      const config = useRuntimeConfig()
      this.isLoading = true
      this.error = null

      try {
        // Appel à l'API d'inscription
        await $fetch(`${config.public.apiBaseUrl}/auth/register`, {
          method: 'POST',
          body: {
            ...userData,
            role: 'customer' // Les nouveaux utilisateurs sont des clients par défaut
          }
        })

        // Connexion automatique après inscription
        return await this.login({
          email: userData.email,
          password: userData.password
        })
      } catch (error: any) {
        this.error = error?.data?.detail || 'Erreur lors de l\'inscription. Veuillez réessayer.'
        console.error('Erreur d\'inscription:', error)
        return false
      } finally {
        this.isLoading = false
      }
    },

    /**
     * Déconnexion de l'utilisateur
     */
    logout() {
      this.user = null
      this.token = null
      this.error = null

      // Suppression des données persistées
      if (import.meta.client) {
        localStorage.removeItem('telia_token')
        localStorage.removeItem('telia_user')
      }

      // Redirection vers la page de connexion
      navigateTo('/login')
    },

    /**
     * Restauration de la session depuis le localStorage
     */
    restoreSession() {
      if (import.meta.client) {
        const token = localStorage.getItem('telia_token')
        const userJson = localStorage.getItem('telia_user')

        if (token && userJson) {
          try {
            this.token = token
            this.user = JSON.parse(userJson)
          } catch {
            // En cas d'erreur de parsing, on nettoie les données
            this.logout()
          }
        }
      }
    },

    /**
     * Récupération des informations utilisateur actuelles depuis l'API
     */
    async fetchCurrentUser(): Promise<boolean> {
      const config = useRuntimeConfig()
      
      if (!this.token) return false

      try {
        const user = await $fetch<User>(`${config.public.apiBaseUrl}/auth/me`, {
          headers: {
            Authorization: `Bearer ${this.token}`
          }
        })

        this.user = user

        // Mise à jour du localStorage
        if (import.meta.client) {
          localStorage.setItem('telia_user', JSON.stringify(user))
        }

        return true
      } catch (error) {
        console.error('Erreur lors de la récupération de l\'utilisateur:', error)
        this.logout()
        return false
      }
    }
  }
})



