<!--
  Page de connexion / inscription
  
  Cette page permet aux utilisateurs de se connecter ou de créer
  un nouveau compte pour accéder à Telia Assistant.
-->
<template>
  <div class="auth-container">
    <!-- Décoration de fond -->
    <div class="auth-background">
      <div class="bg-circle circle-1"></div>
      <div class="bg-circle circle-2"></div>
      <div class="bg-circle circle-3"></div>
    </div>
    
    <div class="auth-card">
      <!-- En-tête avec logo -->
      <div class="auth-header">
        <div class="logo">
          <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="32" cy="32" r="30" fill="#FF6600"/>
            <path d="M20 28C20 26.8954 20.8954 26 22 26H42C43.1046 26 44 26.8954 44 28V44C44 45.1046 43.1046 46 42 46H22C20.8954 46 20 45.1046 20 44V28Z" fill="white"/>
            <path d="M24 22C24 20.8954 24.8954 20 26 20H38C39.1046 20 40 20.8954 40 22V26H24V22Z" fill="white"/>
            <circle cx="28" cy="34" r="3" fill="#FF6600"/>
            <circle cx="36" cy="34" r="3" fill="#FF6600"/>
            <path d="M28 40C28 40 30 42 32 42C34 42 36 40 36 40" stroke="#FF6600" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <h1 class="auth-title">Telia Assistant</h1>
        <p class="auth-subtitle">
          {{ isLoginMode ? 'Connectez-vous pour continuer' : 'Créez votre compte' }}
        </p>
      </div>

      <!-- Message d'erreur -->
      <div v-if="authStore.error" class="error-message">
        <svg class="error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="12" cy="12" r="10" stroke-width="2"/>
          <path d="M12 8v4M12 16h.01" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>{{ authStore.error }}</span>
      </div>

      <!-- Formulaire de connexion -->
      <form v-if="isLoginMode" @submit.prevent="handleLogin" class="auth-form">
        <div class="form-group">
          <label class="form-label" for="login-email">Email ou nom d'utilisateur</label>
          <input
            id="login-email"
            v-model="loginForm.email"
            type="text"
            class="form-input"
            placeholder="votre@email.com"
            required
            autocomplete="username"
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="login-password">Mot de passe</label>
          <div class="password-input">
            <input
              id="login-password"
              v-model="loginForm.password"
              :type="showPassword ? 'text' : 'password'"
              class="form-input"
              placeholder="••••••••"
              required
              autocomplete="current-password"
            />
            <button 
              type="button" 
              class="password-toggle"
              @click="showPassword = !showPassword"
            >
              <svg v-if="showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" stroke-width="2" stroke-linecap="round"/>
                <line x1="1" y1="1" x2="23" y2="23" stroke-width="2"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke-width="2"/>
                <circle cx="12" cy="12" r="3" stroke-width="2"/>
              </svg>
            </button>
          </div>
        </div>

        <button 
          type="submit" 
          class="btn btn-primary btn-full"
          :disabled="authStore.isLoading"
        >
          <span v-if="authStore.isLoading" class="spinner"></span>
          <span v-else>Se connecter</span>
        </button>
      </form>

      <!-- Formulaire d'inscription -->
      <form v-else @submit.prevent="handleRegister" class="auth-form">
        <div class="form-group">
          <label class="form-label" for="register-name">Nom complet</label>
          <input
            id="register-name"
            v-model="registerForm.full_name"
            type="text"
            class="form-input"
            placeholder="Jean Dupont"
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="register-username">Nom d'utilisateur</label>
          <input
            id="register-username"
            v-model="registerForm.username"
            type="text"
            class="form-input"
            placeholder="jean_dupont"
            required
            minlength="3"
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="register-email">Email</label>
          <input
            id="register-email"
            v-model="registerForm.email"
            type="email"
            class="form-input"
            placeholder="votre@email.com"
            required
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="register-password">Mot de passe</label>
          <div class="password-input">
            <input
              id="register-password"
              v-model="registerForm.password"
              :type="showPassword ? 'text' : 'password'"
              class="form-input"
              placeholder="Min. 8 caractères"
              required
              minlength="8"
            />
            <button 
              type="button" 
              class="password-toggle"
              @click="showPassword = !showPassword"
            >
              <svg v-if="showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" stroke-width="2" stroke-linecap="round"/>
                <line x1="1" y1="1" x2="23" y2="23" stroke-width="2"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke-width="2"/>
                <circle cx="12" cy="12" r="3" stroke-width="2"/>
              </svg>
            </button>
          </div>
        </div>

        <button 
          type="submit" 
          class="btn btn-primary btn-full"
          :disabled="authStore.isLoading"
        >
          <span v-if="authStore.isLoading" class="spinner"></span>
          <span v-else>Créer un compte</span>
        </button>
      </form>

      <!-- Basculer entre connexion et inscription -->
      <div class="auth-switch">
        <p v-if="isLoginMode">
          Pas encore de compte ?
          <button type="button" @click="isLoginMode = false" class="switch-link">
            Inscrivez-vous
          </button>
        </p>
        <p v-else>
          Déjà un compte ?
          <button type="button" @click="isLoginMode = true" class="switch-link">
            Connectez-vous
          </button>
        </p>
      </div>

      <!-- Lien vers Glotelho -->
      <div class="glotelho-link">
        <a href="https://glotelho.cm" target="_blank" rel="noopener noreferrer">
          Visiter Glotelho.cm
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Script de la page de connexion/inscription
 */
import { useAuthStore } from '~/stores/auth'

// Store d'authentification
const authStore = useAuthStore()

// État du mode (connexion ou inscription)
const isLoginMode = ref(true)

// Affichage du mot de passe
const showPassword = ref(false)

// Formulaire de connexion
const loginForm = reactive({
  email: '',
  password: ''
})

// Formulaire d'inscription
const registerForm = reactive({
  email: '',
  username: '',
  password: '',
  full_name: ''
})

/**
 * Gère la soumission du formulaire de connexion
 */
async function handleLogin() {
  const success = await authStore.login({
    email: loginForm.email,
    password: loginForm.password
  })

  if (success) {
    navigateTo('/chat')
  }
}

/**
 * Gère la soumission du formulaire d'inscription
 */
async function handleRegister() {
  const success = await authStore.register({
    email: registerForm.email,
    username: registerForm.username,
    password: registerForm.password,
    full_name: registerForm.full_name || undefined
  })

  if (success) {
    navigateTo('/chat')
  }
}

// Rediriger si déjà connecté
onMounted(() => {
  if (authStore.isAuthenticated) {
    navigateTo('/chat')
  }
})

// Métadonnées de la page
useHead({
  title: 'Connexion'
})
</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-lg);
  background: #0F1419;  /* Fond noir Glotelho */
  position: relative;
  overflow: hidden;
}

/* Décoration de fond */
.auth-background {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.15;
}

.circle-1 {
  width: 400px;
  height: 400px;
  background: #FF6600;  /* Orange Glotelho */
  top: -100px;
  right: -100px;
}

.circle-2 {
  width: 300px;
  height: 300px;
  background: #FF4757;  /* Rose/Rouge */
  bottom: -50px;
  left: -50px;
}

.circle-3 {
  width: 200px;
  height: 200px;
  background: #FFA500;  /* Orange doré */
  top: 50%;
  left: 10%;
}

/* Carte d'authentification */
.auth-card {
  width: 100%;
  max-width: 420px;
  background: white;
  border-radius: var(--border-radius-xl);
  box-shadow: var(--shadow-xl);
  padding: var(--spacing-2xl);
  position: relative;
  z-index: 1;
  animation: fadeIn 0.5s ease-out;
}

.auth-header {
  text-align: center;
  margin-bottom: var(--spacing-xl);
}

.logo {
  width: 80px;
  height: 80px;
  margin: 0 auto var(--spacing-lg);
}

.logo svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 4px 8px rgba(229, 57, 53, 0.3));
}

.auth-title {
  font-family: 'Poppins', sans-serif;
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: #FF6600;  /* Orange Glotelho */
  margin-bottom: var(--spacing-xs);
}

.auth-subtitle {
  font-family: 'Open Sans', sans-serif;
  font-size: var(--font-size-sm);
  color: #666666;
}

/* Message d'erreur */
.error-message {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background-color: #FEE2E2;
  border: 1px solid #FCA5A5;
  border-radius: var(--border-radius-md);
  color: #991B1B;
  font-size: var(--font-size-sm);
  margin-bottom: var(--spacing-lg);
  animation: fadeIn 0.3s ease-out;
}

.error-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* Formulaire */
.auth-form {
  margin-bottom: var(--spacing-lg);
}

.password-input {
  position: relative;
}

.password-toggle {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  padding: var(--spacing-xs);
  color: var(--color-gray-500);
  transition: color var(--transition-fast);
}

.password-toggle:hover {
  color: var(--color-gray-700);
}

.password-toggle svg {
  width: 20px;
  height: 20px;
}

/* Switch mode */
.auth-switch {
  text-align: center;
  font-size: var(--font-size-sm);
  color: var(--color-gray-600);
}

.switch-link {
  background: none;
  border: none;
  color: #FF6600;  /* Orange Glotelho */
  font-weight: 600;
  cursor: pointer;
  transition: color var(--transition-fast);
}

.switch-link:hover {
  color: #E55C00;
  text-decoration: underline;
}

/* Lien Glotelho */
.glotelho-link {
  text-align: center;
  margin-top: var(--spacing-xl);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--color-gray-200);
}

.glotelho-link a {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  color: var(--color-gray-500);
  font-size: var(--font-size-sm);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.glotelho-link a:hover {
  color: var(--color-primary);
}

.glotelho-link svg {
  width: 16px;
  height: 16px;
}

/* Animation */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Responsive */
@media (max-width: 480px) {
  .auth-card {
    padding: var(--spacing-xl);
  }
  
  .logo {
    width: 60px;
    height: 60px;
  }
  
  .auth-title {
    font-size: var(--font-size-xl);
  }
}
</style>


