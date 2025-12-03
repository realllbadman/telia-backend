<!--
  Composant racine de l'application Telia Assistant
  
  Ce composant est le point d'entrée principal de l'application Nuxt.
  Il utilise NuxtLayout pour la gestion des layouts et NuxtPage pour le routage.
-->
<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>

<script setup lang="ts">
/**
 * Script de configuration du composant App
 * 
 * Ce script utilise la Composition API de Vue 3 avec le mode <script setup>
 * pour une syntaxe plus concise et performante.
 */

// Configuration des métadonnées SEO par défaut
useHead({
  titleTemplate: (titleChunk) => {
    return titleChunk ? `${titleChunk} - Telia Assistant` : 'Telia Assistant - Glotelho'
  }
})
</script>

<style>
/**
 * Styles globaux additionnels pour le composant App
 */
#__nuxt {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>



