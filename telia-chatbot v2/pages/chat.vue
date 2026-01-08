<!--
  Widget Chatbot Telia Assistant
  
  Interface compacte conçue pour être intégrée dans un coin
  du site web Glotelho.cm
-->
<template>
  <div class="widget-wrapper">
    <!-- Bouton flottant pour ouvrir/fermer le chat -->
    <button 
      v-if="!isOpen" 
      class="chat-trigger"
      @click="openChat"
    >
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M21 11.5C21 16.75 16.75 21 11.5 21C6.25 21 2 16.75 2 11.5C2 6.25 6.25 2 11.5 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <path d="M22 2L15 9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <path d="M16 2H22V8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span class="trigger-badge" v-if="unreadCount > 0">{{ unreadCount }}</span>
    </button>

    <!-- Widget de chat -->
    <div v-show="isOpen" class="chat-widget" :class="{ 'widget-minimized': isMinimized, 'widget-fullscreen': isFullscreen }">
      <!-- En-tête du widget -->
      <header class="widget-header" @click="toggleMinimize">
        <div class="header-left">
        <div class="bot-avatar">
          <img src="/logo.jpg" alt="Telia Assistant" class="avatar-img" />
        </div>
          <div class="header-info">
            <span class="bot-name">Telia Assistant</span>
            <span class="bot-status">
              <span class="status-dot"></span>
              En ligne
            </span>
          </div>
        </div>
        <div class="header-actions">
          <button class="header-btn" @click.stop="clearChat" title="Nouvelle conversation">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10 4v12M4 10h12" stroke-linecap="round"/>
            </svg>
          </button>
          <button class="header-btn" @click.stop="toggleFullscreen" :title="isFullscreen ? 'Réduire' : 'Plein écran'">
            <svg v-if="!isFullscreen" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 7V3h4M17 7V3h-4M3 13v4h4M17 13v4h-4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <svg v-else viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M7 3v4H3M13 3v4h4M7 17v-4H3M13 17v-4h4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <button class="header-btn" @click.stop="toggleMinimize" :title="isMinimized ? 'Agrandir' : 'Réduire'">
            <svg v-if="!isMinimized" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 10h12" stroke-linecap="round"/>
            </svg>
            <svg v-else viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="4" y="4" width="12" height="12" rx="1"/>
            </svg>
          </button>
          <button class="header-btn close-btn" @click.stop="closeChat" title="Fermer">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M5 5l10 10M15 5L5 15" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      </header>

      <!-- Corps du chat (caché si minimisé) -->
      <template v-if="!isMinimized">
        <!-- Zone des messages -->
        <main ref="messagesContainer" class="widget-messages">
          <!-- Message de bienvenue si vide -->
          <div v-if="chatStore.isEmpty" class="welcome-box">
            <p class="welcome-text">👋 Bonjour ! Comment puis-je vous aider ?</p>
            <div class="quick-chips">
              <button @click="sendQuickMessage('Je cherche un téléphone')" class="chip">📱 Téléphones</button>
              <button @click="sendQuickMessage('Ordinateurs portables')" class="chip">💻 PC</button>
              <button @click="sendQuickMessage('Promotions du moment')" class="chip">🏷️ Promos</button>
            </div>
          </div>

          <!-- Liste des messages -->
          <div v-else class="messages-list">
            <div
              v-for="message in chatStore.messages"
              :key="message.id"
              :class="['message', `message-${message.role}`]"
            >
              <!-- Avatar bot uniquement -->
              <div v-if="message.role === 'assistant'" class="msg-avatar">
                <img src="/logo.jpg" alt="Telia" class="avatar-img" />
              </div>

              <!-- Contenu du message -->
              <div class="msg-content">
                <!-- Indicateur de frappe -->
                <div v-if="message.isTyping" class="typing-dots">
                  <span></span><span></span><span></span>
                </div>

                <!-- Texte du message -->
                <div v-else class="msg-text" v-html="formatMessage(message.content)"></div>

                <!-- Images attachées -->
                <div v-if="message.images && message.images.length > 0" class="msg-images">
                  <img
                    v-for="img in message.images"
                    :key="img.id"
                    :src="img.url"
                    :alt="img.name"
                    class="msg-image"
                  />
                </div>

                <!-- Produits recommandés - Grille horizontale style Glotelho -->
                <div v-if="message.products && message.products.length > 0" class="products-grid-wrapper">
                  <div class="products-grid">
                    <div
                      v-for="product in message.products"
                      :key="product.id"
                      class="product-card"
                    >
                      <!-- Badge promo -->
                      <span v-if="product.price.has_discount" class="promo-badge">
                        -{{ Math.round(product.price.discount_percentage || 0) }}%
                      </span>
                      
                      <!-- Image du produit -->
                      <div class="card-image">
                        <img
                          v-if="product.images && product.images.length > 0"
                          :src="product.images[0].url"
                          :alt="product.name"
                          loading="lazy"
                          referrerpolicy="no-referrer"
                        />
                        <div v-else class="no-image">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <rect x="3" y="3" width="18" height="18" rx="2"/>
                            <circle cx="8.5" cy="8.5" r="1.5"/>
                            <path d="M21 15l-5-5L5 21"/>
                          </svg>
                        </div>
                      </div>
                      
                      <!-- Infos du produit -->
                      <div class="card-content">
                        <!-- Nom du produit -->
                        <h4 class="card-title">{{ product.name }}</h4>
                        
                        <!-- Prix -->
                        <div class="card-pricing">
                          <span class="current-price">
                            {{ formatPrice(product.price.amount) }}
                          </span>
                          <span v-if="product.price.has_discount && product.price.regular_amount" class="old-price">
                            {{ formatPrice(product.price.regular_amount) }}
                          </span>
                        </div>
                        
                        <!-- Boutons d'action -->
                        <div class="card-actions">
                          <button 
                            class="btn-details"
                            @click="openProductDetails(product)"
                          >
                            👁️ Voir Plus
                          </button>
                          <a 
                            v-if="product.url"
                            :href="product.buy_url || product.url" 
                            target="_blank" 
                            class="btn-buy"
                          >
                            🛒 Acheter
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>

        <!-- Zone de saisie -->
        <footer class="widget-input">
          <!-- Prévisualisation des images -->
          <div v-if="selectedImages.length > 0" class="img-preview">
            <div v-for="(img, index) in selectedImages" :key="img.id" class="preview-thumb">
              <img :src="img.url" :alt="img.name" />
              <button @click="removeImage(index)" class="remove-img">×</button>
            </div>
          </div>

          <form @submit.prevent="handleSendMessage" class="input-row">
            <!-- Bouton image -->
            <input
              ref="imageInput"
              type="file"
              accept="image/*"
              multiple
              class="hidden"
              @change="handleImageSelect"
            />
            <button type="button" class="input-action" @click="$refs.imageInput.click()" title="Ajouter image">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="2" y="2" width="16" height="16" rx="2"/>
                <circle cx="7" cy="7" r="1.5" fill="currentColor"/>
                <path d="M18 13l-4-4-8 8"/>
              </svg>
            </button>

            <!-- Champ texte -->
            <input
              v-model="messageText"
              type="text"
              class="text-input"
              placeholder="Votre message..."
              :disabled="chatStore.isProcessing"
            />

            <!-- Bouton envoi -->
            <button
              type="submit"
              class="send-action"
              :disabled="(!messageText.trim() && selectedImages.length === 0) || chatStore.isProcessing"
            >
              <svg v-if="!chatStore.isProcessing" viewBox="0 0 20 20" fill="currentColor">
                <path d="M2.5 10L17.5 2.5L10 17.5L8.75 11.25L2.5 10Z"/>
              </svg>
              <span v-else class="mini-spinner"></span>
            </button>
          </form>
        </footer>
      </template>
    </div>

    <!-- Modal de détails produit -->
    <Teleport to="body">
      <div v-if="showProductModal && selectedProduct" class="product-modal-overlay" @click.self="closeProductDetails">
        <div class="product-modal">
          <!-- Header du modal -->
          <header class="modal-header">
            <h3>Détails du produit</h3>
            <button class="modal-close" @click="closeProductDetails">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 6l12 12M18 6L6 18" stroke-linecap="round"/>
              </svg>
            </button>
          </header>
          
          <!-- Corps du modal -->
          <div class="modal-body">
            <!-- Image principale -->
            <div class="modal-image">
              <img 
                v-if="selectedProduct.images && selectedProduct.images.length > 0"
                :src="selectedProduct.images[0].url"
                :alt="selectedProduct.name"
                referrerpolicy="no-referrer"
              />
              <div v-else class="no-image-large">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <path d="M21 15l-5-5L5 21"/>
                </svg>
              </div>
              <!-- Badge promo dans le modal -->
              <span v-if="selectedProduct.price.has_discount" class="modal-promo-badge">
                -{{ Math.round(selectedProduct.price.discount_percentage || 0) }}%
              </span>
            </div>
            
            <!-- Informations -->
            <div class="modal-info">
              <h2 class="modal-title">{{ selectedProduct.name }}</h2>
              
              <!-- Prix -->
              <div class="modal-pricing">
                <span class="modal-current-price">
                  {{ formatPrice(selectedProduct.price.amount) }}
                </span>
                <span v-if="selectedProduct.price.has_discount && selectedProduct.price.regular_amount" class="modal-old-price">
                  {{ formatPrice(selectedProduct.price.regular_amount) }}
                </span>
              </div>
              
              <!-- Disponibilité -->
              <div class="modal-availability">
                <span v-if="selectedProduct.is_available" class="available">
                  ✅ En stock
                </span>
                <span v-else class="unavailable">
                  ❌ Rupture de stock
                </span>
              </div>
              
              <!-- Description -->
              <div v-if="selectedProduct.short_description || selectedProduct.description" class="modal-description">
                <h4>Description</h4>
                <p v-html="selectedProduct.short_description || selectedProduct.description"></p>
              </div>
              
              <!-- Caractéristiques -->
              <div v-if="selectedProduct.characteristics && selectedProduct.characteristics.length > 0" class="modal-characteristics">
                <h4>Caractéristiques</h4>
                <ul>
                  <li v-for="char in selectedProduct.characteristics" :key="char.code">
                    <strong>{{ char.label }}:</strong> {{ char.value }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
          
          <!-- Footer du modal avec bouton Acheter -->
          <footer class="modal-footer">
            <a 
              v-if="selectedProduct.url"
              :href="selectedProduct.buy_url || selectedProduct.url" 
              target="_blank" 
              class="modal-btn-buy"
              @click="closeProductDetails"
            >
              🛒 Acheter maintenant
            </a>
            <a 
              v-if="selectedProduct.url"
              :href="selectedProduct.url" 
              target="_blank" 
              class="modal-btn-view"
            >
              🔗 Voir sur le site
            </a>
          </footer>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
/**
 * Script du widget de chat Telia Assistant
 */
import { useAuthStore } from '~/stores/auth'
import { useChatStore, type MessageImage, type Product } from '~/stores/chat'
import { marked } from 'marked'

// Stores
const authStore = useAuthStore()
const chatStore = useChatStore()
const route = useRoute()

// Références
const messagesContainer = ref<HTMLElement | null>(null)
const imageInput = ref<HTMLInputElement | null>(null)

// État du widget
const isOpen = ref(false)
const isMinimized = ref(false)
const isFullscreen = ref(false)
const messageText = ref('')
const selectedImages = ref<MessageImage[]>([])
const unreadCount = ref(0)

/**
 * Ouvre le widget de chat
 */
function openChat() {
  isOpen.value = true
  isMinimized.value = false
  unreadCount.value = 0
  
  // Initialiser la session si nécessaire
  if (chatStore.isEmpty) {
    chatStore.initSession()
  }
}

/**
 * Ferme le widget de chat
 */
function closeChat() {
  isOpen.value = false
}

/**
 * Minimise/agrandit le widget
 */
function toggleMinimize() {
  isMinimized.value = !isMinimized.value
}

/**
 * Active/désactive le mode plein écran
 */
function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  // Désactiver minimize si on passe en fullscreen
  if (isFullscreen.value) {
    isMinimized.value = false
  }
}

/**
 * Scroll automatique vers le bas
 */
watch(() => chatStore.messages.length, () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
  
  // Incrémenter compteur si widget fermé
  if (!isOpen.value) {
    unreadCount.value++
  }
})

/**
 * Gère l'envoi d'un message
 */
async function handleSendMessage() {
  const text = messageText.value.trim()
  const images = [...selectedImages.value]

  if (!text && images.length === 0) return

  messageText.value = ''
  selectedImages.value = []

  await chatStore.sendMessage(text, images)
}

/**
 * Envoie un message rapide
 */
function sendQuickMessage(text: string) {
  messageText.value = text
  handleSendMessage()
}

/**
 * Gère la sélection d'images
 */
function handleImageSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files

  if (!files) return

  Array.from(files).forEach(file => {
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (e) => {
        selectedImages.value.push({
          id: `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          url: e.target?.result as string,
          name: file.name,
          type: file.type
        })
      }
      reader.readAsDataURL(file)
    }
  })

  input.value = ''
}

/**
 * Supprime une image sélectionnée
 */
function removeImage(index: number) {
  selectedImages.value.splice(index, 1)
}

/**
 * Efface l'historique
 */
function clearChat() {
  chatStore.clearHistory()
}

/**
 * Formate le message avec markdown (utilise marked)
 */
function formatMessage(content: string): string {
  if (!content) return ''
  try {
    return marked.parse(content, { breaks: true, async: false }) as string
  } catch (e) {
    console.error('Erreur parsing markdown:', e)
    return content
  }
}



/**
 * Formate un prix en XAF et nettoie le HTML éventuel
 */
function formatPrice(price: number | string | null): string {
  // Si c'est nul ou indéfini
  if (price === null || price === undefined) return 'Prix N/D'
  
  // Si c'est une chaîne qui contient du HTML ou qu'on veut nettoyer
  if (typeof price === 'string') {
    // Enlever les balises HTML si présentes (compatible SSR avec regex)
    if (price.includes('<')) {
      price = price.replace(/<[^>]*>/g, '')
    }
    
    // Essayer de convertir en nombre
    const num = parseFloat(price.replace(/[^0-9.-]+/g, ''))
    if (!isNaN(num)) price = num
  }

  // Si c'est un nombre valide
  if (typeof price === 'number') {
    return new Intl.NumberFormat('fr-CM', {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0 // Pas de centimes pour les FCFA généralement
    }).format(price)
  }

  return String(price)
}

// État pour le modal de détails produit
const selectedProduct = ref<any>(null)
const showProductModal = ref(false)

/**
 * Ouvre le modal avec les détails du produit
 */
function openProductDetails(product: any) {
  selectedProduct.value = product
  showProductModal.value = true
}

/**
 * Ferme le modal de détails
 */
function closeProductDetails() {
  selectedProduct.value = null
  showProductModal.value = false
}

// Ouvrir automatiquement si authentifié
onMounted(() => {
  if (!authStore.isAuthenticated) {
    navigateTo('/login')
    return
  }
  
  // Ouvrir automatiquement le widget
  setTimeout(() => {
    openChat()
  }, 500)
})

// Métadonnées
useHead({
  title: 'Telia Assistant'
})

definePageMeta({
  middleware: 'auth'
})
</script>

<style scoped>
/* ============================================
   Variables du widget - Thème Officiel Glotelho.cm
   ============================================ */
.widget-wrapper {
  /* Couleurs Glotelho */
  --widget-primary: #FF6600;           /* Orange Vif */
  --widget-primary-dark: #E55C00;      /* Orange foncé */
  --widget-secondary: #FF4757;         /* Rose/Rouge */
  --widget-dark: #0F1419;              /* Noir profond */
  --widget-promo: #FFA500;             /* Orange doré */
  --widget-urgent: #E63946;            /* Rouge écarlate */
  
  /* Fonds */
  --widget-bg: #FFFFFF;
  --widget-surface: #F5F5F5;
  
  /* Textes */
  --widget-text: #333333;              /* Texte principal */
  --widget-text-secondary: #666666;    /* Texte secondaire */
  --widget-text-light: #999999;        /* Texte léger */
  
  /* Bordures et ombres */
  --widget-border: #E0E0E0;
  --widget-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  --widget-radius: 16px;
  
  /* Typographie Glotelho */
  --font-heading: 'Poppins', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-body: 'Open Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 99999;
  font-family: var(--font-body);
}

/* ============================================
   Bouton déclencheur flottant - Style Glotelho
   ============================================ */
.chat-trigger {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: var(--widget-primary);  /* Orange Glotelho */
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--widget-shadow);
  transition: transform 0.2s, box-shadow 0.2s, background 0.2s;
  position: relative;
}

.chat-trigger:hover {
  transform: scale(1.08);
  background: var(--widget-primary-dark);
  box-shadow: 0 12px 40px rgba(255, 102, 0, 0.4);
}

.chat-trigger svg {
  width: 28px;
  height: 28px;
  color: white;
}

.trigger-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 22px;
  height: 22px;
  background: var(--widget-urgent);  /* Rouge écarlate */
  color: white;
  font-family: var(--font-heading);
  font-size: 12px;
  font-weight: 700;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid white;
}

/* ============================================
   Widget de chat
   ============================================ */
.chat-widget {
  width: 380px;
  max-width: calc(100vw - 48px);
  height: 520px;
  max-height: calc(100vh - 100px);
  background: var(--widget-bg);
  border-radius: var(--widget-radius);
  box-shadow: var(--widget-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.3s ease-out;
}

.widget-minimized {
  height: auto;
}

.widget-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw !important;
  max-width: 100vw !important;
  height: 100vh !important;
  max-height: 100vh !important;
  border-radius: 0;
  z-index: 999999;
}

.widget-fullscreen .widget-header {
  padding: 16px 24px;
}

.widget-fullscreen .bot-avatar {
  width: 44px;
  height: 44px;
}

.widget-fullscreen .bot-name {
  font-size: 16px;
}

.widget-fullscreen .bot-status {
  font-size: 12px;
}

.widget-fullscreen .header-btn {
  width: 36px;
  height: 36px;
}

.widget-fullscreen .header-btn svg {
  width: 18px;
  height: 18px;
}

.widget-fullscreen .widget-messages {
  padding: 24px;
}

.widget-fullscreen .messages-list {
  max-width: 800px;
  margin: 0 auto;
}

.widget-fullscreen .msg-text {
  font-size: 15px;
  padding: 12px 18px;
}

.widget-fullscreen .msg-avatar {
  width: 36px;
  height: 36px;
}

.widget-fullscreen .widget-input {
  padding: 16px 24px;
}

.widget-fullscreen .input-row {
  max-width: 800px;
  margin: 0 auto;
  padding: 6px;
}

.widget-fullscreen .text-input {
  font-size: 15px;
}

.widget-fullscreen .input-action,
.widget-fullscreen .send-action {
  width: 44px;
  height: 44px;
}

.widget-fullscreen .quick-chips {
  gap: 12px;
}

.widget-fullscreen .chip {
  padding: 12px 20px;
  font-size: 14px;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* ============================================
   En-tête du widget - Style Glotelho
   ============================================ */
.widget-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--widget-dark);  /* Fond noir Glotelho */
  color: white;
  cursor: pointer;
  user-select: none;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bot-avatar {
  width: 44px; /* Un peu plus grand pour l'entête */
  height: 44px;
  border-radius: 50%;
  margin-right: 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  padding: 0;
  overflow: hidden;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.bot-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scale(1.15); /* Zoom pour compenser les marges de l'image */
}

.header-info {
  display: flex;
  flex-direction: column;
}

.bot-name {
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 700;
  color: var(--widget-primary);  /* Orange Glotelho */
}

.bot-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  opacity: 0.9;
  color: #FFFFFF;
}

.status-dot {
  width: 6px;
  height: 6px;
  background: #4AE54A;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.header-actions {
  display: flex;
  gap: 4px;
}

.header-btn {
  width: 28px;
  height: 28px;
  background: rgba(255, 255, 255, 0.15);
  border: none;
  border-radius: 6px;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.header-btn:hover {
  background: rgba(255, 255, 255, 0.25);
}

.header-btn svg {
  width: 14px;
  height: 14px;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* ============================================
   Zone des messages
   ============================================ */
.widget-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden; /* Important pour éviter le scroll horizontal */
  padding: 16px;
  background: var(--widget-surface);
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  max-width: 100%;
}

/* Message de bienvenue - Style Glotelho */
.welcome-box {
  text-align: center;
  padding: 20px 10px;
}

.welcome-text {
  font-family: var(--font-body);
  font-size: 15px;
  color: var(--widget-text);
  margin-bottom: 16px;
}

.quick-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.chip {
  padding: 8px 14px;
  background: white;
  border: 1px solid var(--widget-border);
  border-radius: 20px;
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--widget-text);
  cursor: pointer;
  transition: all 0.2s;
}

.chip:hover {
  border-color: var(--widget-primary);
  color: var(--widget-primary);
  background: #FFF8F0;  /* Orange très léger */
}

/* Liste des messages */
.messages-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message {
  display: flex;
  gap: 8px;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Message entrant */
.message-assistant {
  align-self: flex-start;
  background: #f1f3f5;
  color: var(--widget-dark);
  border-bottom-left-radius: 4px;
  max-width: 88%; /* Limite la largeur du message par rapport au chat */
  width: auto;
}

.message-user {
  flex-direction: row-reverse;
  max-width: 88%;
  align-self: flex-end;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  margin-right: 8px;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  background: transparent;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scale(1.15);
}

.msg-content {
  flex: 1; /* Prend l'espace restant */
  min-width: 0; /* CRUCIAL: Permet au flex item de rétrécir sous son contenu minimum */
  width: 100%;
}

.msg-text {
  padding: 12px 16px;
  border-radius: 14px;
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.5;
  width: fit-content; /* S'adapte au contenu mais respecte max-width du parent */
  max-width: 100%;    /* Ne dépasse jamais son parent (.msg-content) */
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
}

/* Styles pour le Markdown (Tableaux, etc.) */
.msg-text :deep(p) {
  margin-bottom: 8px;
}
.msg-text :deep(p:last-child) {
  margin-bottom: 0;
}
.msg-text :deep(ul), .msg-text :deep(ol) {
  margin-left: 20px;
  margin-bottom: 8px;
}
.msg-text :deep(table) {
  display: block;
  width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 13px;
}
.msg-text :deep(th), .msg-text :deep(td) {
  border: 1px solid #e0e0e0;
  padding: 6px 10px;
  text-align: left;
}
.msg-text :deep(th) {
  background-color: #f5f5f5;
  font-weight: 600;
}
.msg-text :deep(a) {
  color: var(--widget-primary);
  text-decoration: underline;
}

.message-assistant .msg-text {
  background: white;
  color: var(--widget-text);
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.message-user .msg-text {
  background: var(--widget-primary);  /* Orange Glotelho */
  color: white;
  border-bottom-right-radius: 4px;
}

/* Indicateur de frappe */
.typing-dots {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: white;
  border-radius: 14px;
  border-bottom-left-radius: 4px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  background: var(--widget-text-light);
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-4px); }
}

/* Images dans les messages */
.msg-images {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.msg-image {
  max-width: 120px;
  max-height: 120px;
  border-radius: 8px;
  object-fit: cover;
}

/* ============================================
   Grille de produits - Style Glotelho
   ============================================ */
.products-grid-wrapper {
  margin-top: 12px;
  width: 100%;
  overflow: hidden;
}

.products-grid {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding: 4px 0 8px 0;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--widget-primary) transparent;
}

.products-grid::-webkit-scrollbar {
  height: 4px;
}

.products-grid::-webkit-scrollbar-track {
  background: transparent;
}

.products-grid::-webkit-scrollbar-thumb {
  background: var(--widget-primary);
  border-radius: 2px;
}

/* Card produit */
.product-card {
  flex: 0 0 160px;
  min-width: 160px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  scroll-snap-align: start;
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
}

.product-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

/* Badge promo */
.promo-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 3px 8px;
  background: linear-gradient(135deg, #E63946, #FF6B6B);
  color: white;
  font-family: var(--font-heading);
  font-size: 11px;
  font-weight: 700;
  border-radius: 4px;
  z-index: 2;
  box-shadow: 0 2px 4px rgba(230, 57, 70, 0.3);
}

/* Image du produit */
.card-image {
  width: 100%;
  height: 120px;
  background: #f8f8f8;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.card-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transition: transform 0.3s;
}

.product-card:hover .card-image img {
  transform: scale(1.05);
}

.no-image {
  width: 48px;
  height: 48px;
  color: #ccc;
}

.no-image svg {
  width: 100%;
  height: 100%;
}

/* Contenu de la card */
.card-content {
  padding: 10px;
}

.card-title {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  color: var(--widget-text);
  margin: 0 0 6px 0;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 32px;
}

/* Prix */
.card-pricing {
  margin-bottom: 8px;
}

.current-price {
  display: block;
  font-family: var(--font-heading);
  font-size: 14px;
  font-weight: 700;
  color: var(--widget-dark);
}

.old-price {
  display: block;
  font-family: var(--font-body);
  font-size: 11px;
  color: var(--widget-text-light);
  text-decoration: line-through;
  margin-top: 2px;
}

/* Boutons d'action */
.card-actions {
  display: flex;
  gap: 6px;
}

.btn-details,
.btn-buy {
  flex: 1;
  padding: 6px 8px;
  border-radius: 6px;
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 600;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
}

.btn-details {
  background: var(--widget-surface);
  color: var(--widget-text);
}

.btn-details:hover {
  background: var(--widget-border);
}

.btn-buy {
  background: var(--widget-primary);
  color: white;
}

.btn-buy:hover {
  background: var(--widget-primary-dark);
}

/* ============================================
   Zone de saisie
   ============================================ */
.widget-input {
  padding: 12px;
  background: white;
  border-top: 1px solid var(--widget-border);
}

.img-preview {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  overflow-x: auto;
}

.preview-thumb {
  position: relative;
  width: 50px;
  height: 50px;
  flex-shrink: 0;
}

.preview-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
}

.remove-img {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  background: var(--widget-primary);
  color: white;
  border: none;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--widget-surface);
  border-radius: 24px;
  padding: 4px;
}

.hidden {
  display: none;
}

.input-action {
  width: 36px;
  height: 36px;
  background: transparent;
  border: none;
  border-radius: 50%;
  color: var(--widget-text-light);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
}

.input-action:hover {
  color: var(--widget-primary);
}

.input-action svg {
  width: 18px;
  height: 18px;
}

.text-input {
  flex: 1;
  border: none;
  background: transparent;
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--widget-text);
  outline: none;
}

.text-input::placeholder {
  color: var(--widget-text-light);
}

.send-action {
  width: 36px;
  height: 36px;
  background: var(--widget-primary);  /* Orange Glotelho */
  border: none;
  border-radius: 50%;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, transform 0.2s;
}

.send-action:hover:not(:disabled) {
  background: var(--widget-primary-dark);
  transform: scale(1.05);
}

.send-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-action svg {
  width: 16px;
  height: 16px;
}

.mini-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ============================================
   Modal de détails produit
   ============================================ */
.product-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999999;
  padding: 20px;
  animation: fadeIn 0.2s ease-out;
}

.product-modal {
  background: white;
  border-radius: 16px;
  width: 100%;
  max-width: 420px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: modalSlideUp 0.3s ease-out;
}

@keyframes modalSlideUp {
  from {
    opacity: 0;
    transform: translateY(30px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Header du modal */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: var(--widget-dark);
  color: white;
}

.modal-header h3 {
  font-family: var(--font-heading);
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.modal-close {
  width: 32px;
  height: 32px;
  background: rgba(255, 255, 255, 0.15);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.25);
}

.modal-close svg {
  width: 18px;
  height: 18px;
}

/* Corps du modal */
.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

/* Image dans le modal */
.modal-image {
  position: relative;
  width: 100%;
  height: 200px;
  background: #f8f8f8;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.no-image-large {
  width: 80px;
  height: 80px;
  color: #ccc;
}

.no-image-large svg {
  width: 100%;
  height: 100%;
}

.modal-promo-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 6px 12px;
  background: linear-gradient(135deg, #E63946, #FF6B6B);
  color: white;
  font-family: var(--font-heading);
  font-size: 14px;
  font-weight: 700;
  border-radius: 6px;
  box-shadow: 0 3px 10px rgba(230, 57, 70, 0.4);
}

/* Informations du modal */
.modal-info {
  padding: 20px;
}

.modal-title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  color: var(--widget-dark);
  margin: 0 0 12px 0;
  line-height: 1.4;
}

/* Prix dans le modal */
.modal-pricing {
  margin-bottom: 12px;
}

.modal-current-price {
  font-family: var(--font-heading);
  font-size: 24px;
  font-weight: 700;
  color: var(--widget-primary);
}

.modal-old-price {
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--widget-text-light);
  text-decoration: line-through;
  margin-left: 10px;
}

/* Disponibilité */
.modal-availability {
  margin-bottom: 16px;
}

.modal-availability .available {
  color: #22c55e;
  font-weight: 600;
}

.modal-availability .unavailable {
  color: #ef4444;
  font-weight: 600;
}

/* Description */
.modal-description {
  margin-bottom: 16px;
}

.modal-description h4,
.modal-characteristics h4 {
  font-family: var(--font-heading);
  font-size: 14px;
  font-weight: 600;
  color: var(--widget-dark);
  margin: 0 0 8px 0;
}

.modal-description p {
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--widget-text-secondary);
  line-height: 1.6;
  margin: 0;
}

/* Caractéristiques */
.modal-characteristics ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.modal-characteristics li {
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--widget-text);
  padding: 6px 0;
  border-bottom: 1px solid var(--widget-border);
}

.modal-characteristics li:last-child {
  border-bottom: none;
}

.modal-characteristics strong {
  color: var(--widget-text-secondary);
}

/* Footer du modal */
.modal-footer {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: var(--widget-surface);
  border-top: 1px solid var(--widget-border);
}

.modal-btn-buy,
.modal-btn-view {
  flex: 1;
  padding: 14px 20px;
  border-radius: 10px;
  font-family: var(--font-heading);
  font-size: 14px;
  font-weight: 600;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.modal-btn-buy {
  background: var(--widget-primary);
  color: white;
  box-shadow: 0 4px 14px rgba(255, 102, 0, 0.4);
}

.modal-btn-buy:hover {
  background: var(--widget-primary-dark);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(255, 102, 0, 0.5);
}

.modal-btn-view {
  background: white;
  color: var(--widget-primary);
  border: 2px solid var(--widget-primary);
}

.modal-btn-view:hover {
  background: #fff8f0;
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 480px) {
  .widget-wrapper {
    bottom: 16px;
    right: 16px;
  }
  
  .chat-widget {
    width: calc(100vw - 32px);
    height: calc(100vh - 120px);
    border-radius: 12px;
  }
  
  .chat-trigger {
    width: 54px;
    height: 54px;
  }
  
  .widget-fullscreen {
    border-radius: 0;
  }
  
  .widget-fullscreen .widget-messages {
    padding: 16px;
  }
  
  .widget-fullscreen .widget-input {
    padding: 12px 16px;
  }
}
</style>
