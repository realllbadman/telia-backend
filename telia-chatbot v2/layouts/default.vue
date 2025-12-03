<!--
  Layout par défaut de l'application Telia Assistant
  
  Ce layout fournit la structure de base pour toutes les pages,
  incluant un slot pour le contenu principal.
-->
<template>
  <div class="app-layout">
    <slot />
  </div>
</template>

<script setup lang="ts">
/**
 * Layout par défaut
 * 
 * Gère la restauration de session utilisateur au montage
 */
import { useAuthStore } from '~/stores/auth'

const authStore = useAuthStore()

// Restaurer la session au montage du composant
onMounted(() => {
  authStore.restoreSession()
})
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>



