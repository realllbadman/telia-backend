/**
 * Store Pinia pour la gestion du chat
 * 
 * Ce store gère l'état de la conversation avec Telia Assistant,
 * incluant les messages, les produits recommandés et les commandes.
 */

import { defineStore } from 'pinia'

// Interface pour une image attachée à un message
export interface MessageImage {
  id: string
  url: string        // URL de l'image (base64 ou URL externe)
  name: string       // Nom du fichier
  type: string       // Type MIME
}

// Interface pour un produit Magento
export interface Product {
  id: number
  name: string
  type: string
  url: string | null
  store_id: number
  currency_code: string
  is_salable: boolean
  price_info: {
    final_price: number | null
    regular_price: number | null
    formatted_final_price: string | null
    formatted_regular_price: string | null
  }
  images: Array<{
    url: string
    label: string | null
  }>
}

// Interface pour un message du chat
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  images?: MessageImage[]
  products?: Product[]
  isTyping?: boolean
}

// Interface pour l'état du store
interface ChatState {
  messages: ChatMessage[]
  isProcessing: boolean
  error: string | null
  sessionId: string | null
}

/**
 * Génère un identifiant unique pour les messages
 */
function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

export const useChatStore = defineStore('chat', {
  /**
   * État initial du store de chat
   */
  state: (): ChatState => ({
    messages: [],
    isProcessing: false,
    error: null,
    sessionId: null
  }),

  /**
   * Getters pour accéder aux données calculées
   */
  getters: {
    // Récupère le dernier message
    lastMessage: (state): ChatMessage | null => {
      return state.messages.length > 0 
        ? state.messages[state.messages.length - 1] 
        : null
    },
    
    // Compte le nombre de messages
    messageCount: (state): number => state.messages.length,
    
    // Vérifie si le chat est vide
    isEmpty: (state): boolean => state.messages.length === 0
  },

  /**
   * Actions pour modifier l'état
   */
  actions: {
    /**
     * Initialise une nouvelle session de chat
     */
    initSession() {
      this.sessionId = `session_${Date.now()}`
      this.messages = []
      this.error = null
      
      // Message de bienvenue de Telia
      this.addMessage({
        role: 'assistant',
        content: `🛒 **Bienvenue sur Telia Assistant !**\n\nJe suis votre assistant shopping intelligent pour Glotelho. Je peux vous aider à :\n\n• 🔍 **Trouver des produits** selon vos besoins\n• 📸 **Analyser des images** de produits que vous recherchez\n• 💰 **Comparer les prix** et trouver les meilleures offres\n• 🛍️ **Passer des commandes** directement\n• 📦 **Suivre vos commandes** en cours\n\nComment puis-je vous aider aujourd'hui ?`
      })
    },

    /**
     * Ajoute un message à la conversation
     * 
     * @param message - Données du message (sans id ni timestamp)
     */
    addMessage(message: Omit<ChatMessage, 'id' | 'timestamp'>) {
      const newMessage: ChatMessage = {
        ...message,
        id: generateId(),
        timestamp: new Date()
      }
      this.messages.push(newMessage)
    },

    /**
     * Met à jour un message existant
     * 
     * @param messageId - ID du message à mettre à jour
     * @param updates - Données à mettre à jour
     */
    updateMessage(messageId: string, updates: Partial<ChatMessage>) {
      const index = this.messages.findIndex(m => m.id === messageId)
      if (index !== -1) {
        this.messages[index] = { ...this.messages[index], ...updates }
      }
    },

    /**
     * Envoie un message utilisateur et attend la réponse de l'assistant
     * 
     * @param content - Contenu textuel du message
     * @param images - Images attachées au message (optionnel)
     */
    async sendMessage(content: string, images: MessageImage[] = []) {
      // Ajout du message utilisateur
      this.addMessage({
        role: 'user',
        content,
        images: images.length > 0 ? images : undefined
      })

      // Indicateur de traitement
      this.isProcessing = true
      this.error = null

      // Message de typing de l'assistant
      const typingId = generateId()
      this.messages.push({
        id: typingId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isTyping: true
      })

      try {
        // Appel à l'API server pour traiter le message avec Gemini
        const response = await $fetch<{
          content: string
          products?: Product[]
        }>('/api/chat', {
          method: 'POST',
          body: {
            message: content,
            images: images.map(img => ({
              data: img.url,
              mimeType: img.type
            })),
            history: this.messages
              .filter(m => !m.isTyping)
              .slice(-10) // Limite l'historique aux 10 derniers messages
              .map(m => ({
                role: m.role,
                content: m.content
              }))
          }
        })

        // Suppression du message de typing
        const typingIndex = this.messages.findIndex(m => m.id === typingId)
        if (typingIndex !== -1) {
          this.messages.splice(typingIndex, 1)
        }

        // Ajout de la réponse de l'assistant
        this.addMessage({
          role: 'assistant',
          content: response.content,
          products: response.products
        })

      } catch (error: any) {
        // Suppression du message de typing en cas d'erreur
        const typingIndex = this.messages.findIndex(m => m.id === typingId)
        if (typingIndex !== -1) {
          this.messages.splice(typingIndex, 1)
        }

        this.error = error?.data?.message || 'Une erreur est survenue. Veuillez réessayer.'
        console.error('Erreur lors de l\'envoi du message:', error)

        // Message d'erreur de l'assistant
        this.addMessage({
          role: 'assistant',
          content: `❌ Désolé, une erreur est survenue lors du traitement de votre demande. Veuillez réessayer.`
        })
      } finally {
        this.isProcessing = false
      }
    },

    /**
     * Efface l'historique de la conversation
     */
    clearHistory() {
      this.messages = []
      this.error = null
      this.initSession()
    }
  }
})



