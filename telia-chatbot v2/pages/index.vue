<!--
  Page d'accueil - Redirection vers le chat ou le login
  
  Cette page vérifie l'état d'authentification et redirige
  l'utilisateur vers la page appropriée.
-->
<template>
  <div class="loading-container">
    <div class="loading-content">
      <!-- Logo Telia - Style Glotelho -->
      <div class="logo-container">
        <div class="logo-icon">
          <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="32" cy="32" r="30" fill="#FF6600"/>
            <path d="M20 28C20 26.8954 20.8954 26 22 26H42C43.1046 26 44 26.8954 44 28V44C44 45.1046 43.1046 46 42 46H22C20.8954 46 20 45.1046 20 44V28Z" fill="white"/>
            <path d="M24 22C24 20.8954 24.8954 20 26 20H38C39.1046 20 40 20.8954 40 22V26H24V22Z" fill="white"/>
            <circle cx="28" cy="34" r="3" fill="#FF6600"/>
            <circle cx="36" cy="34" r="3" fill="#FF6600"/>
            <path d="M28 40C28 40 30 42 32 42C34 42 36 40 36 40" stroke="#FF6600" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
      </div>
      
      <!-- Texte de chargement -->
      <h1 class="loading-title">Telia Assistant</h1>
      <p class="loading-text">Chargement en cours...</p>
      
      <!-- Spinner -->
      <div class="spinner"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Page d'accueil avec redirection automatique
 */
import { useAuthStore } from '~/stores/auth'

const authStore = useAuthStore()

// Redirection basée sur l'état d'authentification
onMounted(async () => {
  // Attendre un court instant pour l'animation de chargement
  await new Promise(resolve => setTimeout(resolve, 500))
  
  // Vérifier si l'utilisateur est connecté
  if (authStore.isAuthenticated) {
    navigateTo('/chat')
  } else {
    navigateTo('/login')
  }
})

// Métadonnées de la page
useHead({
  title: 'Accueil'
})
</script>

<style scoped>
.loading-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0F1419;  /* Fond noir Glotelho */
}

.loading-content {
  text-align: center;
  color: white;
}

.logo-container {
  margin-bottom: var(--spacing-xl);
}

.logo-icon {
  width: 100px;
  height: 100px;
  margin: 0 auto;
  animation: bounce 2s infinite;
}

.logo-icon svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.3));
}

.loading-title {
  font-family: 'Poppins', sans-serif;
  font-size: var(--font-size-3xl);
  font-weight: 700;
  color: #FF6600;  /* Orange Glotelho */
  margin-bottom: var(--spacing-sm);
}

.loading-text {
  font-family: 'Open Sans', sans-serif;
  font-size: var(--font-size-base);
  color: #FFFFFF;
  opacity: 0.9;
  margin-bottom: var(--spacing-xl);
}

.spinner {
  width: 40px;
  height: 40px;
  margin: 0 auto;
  border: 4px solid rgba(255, 102, 0, 0.3);
  border-top-color: #FF6600;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes bounce {
  0%, 20%, 53%, 80%, 100% {
    transform: translateY(0);
  }
  40%, 43% {
    transform: translateY(-15px);
  }
  70% {
    transform: translateY(-7px);
  }
}
</style>


