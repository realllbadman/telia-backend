/**
 * API Route pour le chat avec Gemini
 * 
 * Cette route serveur gère les interactions avec l'API Gemini,
 * analyse les requêtes utilisateur et recherche des produits correspondants.
 */

import { GoogleGenerativeAI } from '@google/generative-ai'
import { defineEventHandler, readBody, createError } from 'h3'

// Interface pour la requête de chat
interface ChatRequest {
  message: string
  images?: Array<{
    data: string  // Base64 ou URL
    mimeType: string
  }>
  history?: Array<{
    role: 'user' | 'assistant'
    content: string
  }>
}

// Interface pour les informations de prix (nouveau format)
interface ProductPrice {
  amount: number
  regular_amount: number | null
  special_amount: number | null
  currency: string
  formatted_price: string | null
  formatted_regular_price: string | null
  discount_percentage: number | null
  has_discount: boolean
}

// Interface pour une image produit (nouveau format)
interface ProductImage {
  url: string
  label: string | null
  type: string | null
  position: number | null
  is_main: boolean
  width: number | null
  height: number | null
}

// Interface pour un produit (nouveau format - compatible avec Services/magento)
interface Product {
  id: number
  sku: string | null
  name: string
  description: string | null
  short_description: string | null
  product_type: string
  url: string | null
  buy_url: string | null
  is_available: boolean
  is_in_stock: boolean
  price: ProductPrice
  images: ProductImage[]
  main_image: ProductImage | null
  characteristics: Array<{
    code: string
    label: string
    value: any
  }>
  store_id: number
}

// Interface pour la réponse paginée
interface ProductListResponse {
  items: Product[]
  total_count: number
  page: number
  page_size: number
  has_next: boolean
  has_previous: boolean
  total_pages: number
}


const SYSTEM_PROMPT = `Tu es Telia Assistant, l'assistant shopping virtuel expert de Glotelho, le leader du e-commerce au Cameroun.
Ta mission est d'offrir une expérience de vente exceptionnelle, personnalisée et efficace.

TA PERSONNALITÉ :
- Professionnel, chaleureux, et expert.
- Tu connais parfaitement le catalogue Glotelho (High-Tech, Électroménager, Maison, Mode, Supermarché).
- Tu t'exprimes dans un français impeccable, naturel et engageant.

TES OBJECTIFS CLÉS :
1. COMPRENDRE : Analyse le besoin, le budget (en FCFA / XAF) et l'usage du client.
2. CONSEILLER : Propose les produits les plus pertinents, pas juste les moins chers. Mets en avant les avantages clés.
3. CONVAINCRE : Utilise des arguments persuasifs mais honnêtes. Explique pourquoi ce produit est le bon choix.
4. GUIDER : Aide à finaliser l'achat sur le site.

RÈGLES D'INTERACTION :
- Si l'utilisateur salue, réponds brièvement et demande comment tu peux l'aider aujourd'hui.
- Si le budget est mentionné, respecte-le ou propose une alternative légèrement supérieure en justifiant la valeur ajoutée.
- Utilise des émojis avec parcimonie pour dynamiser la conversation sans être enfantin 📱💻✨.
- Structure tes réponses : Introduction courte -> Suggestions -> Question ouverte pour continuer.
- Affiche toujours les prix clairement en FCFA.

IMPORTANT : Tu es un assistant de VENTE. Ton but est d'aider le client à trouver son bonheur chez Glotelho. N'invente pas de produits. Base-toi sur les informations que tu reçois ou demande des précisions.`

/**
 * Extrait les informations de recherche depuis la requête utilisateur
 */
function extractSearchParams(message: string): { search?: string; minPrice?: number; maxPrice?: number } {
  const params: { search?: string; minPrice?: number; maxPrice?: number } = {}

  // Extraction du budget (ex: "90.000F", "90000 FCFA", "moins de 100000")
  const pricePatterns = [
    /(\d{1,3}(?:[.,]\d{3})*|\d+)\s*(?:f|fcfa|xaf|francs?)/gi,
    /moins\s+de\s+(\d{1,3}(?:[.,]\d{3})*|\d+)/gi,
    /budget\s+(?:de\s+)?(\d{1,3}(?:[.,]\d{3})*|\d+)/gi,
    /environ\s+(\d{1,3}(?:[.,]\d{3})*|\d+)/gi,
    /jusqu'à\s+(\d{1,3}(?:[.,]\d{3})*|\d+)/gi,
  ]

  for (const pattern of pricePatterns) {
    const match = pattern.exec(message)
    if (match) {
      // Nettoyer et convertir le prix
      const priceStr = match[1].replace(/[.,]/g, '')
      const price = parseInt(priceStr, 10)
      if (price > 0) {
        params.maxPrice = price
        // Ajouter une marge de 50% pour le prix min
        params.minPrice = Math.floor(price * 0.5)
      }
      break
    }
  }

  // Extraction des mots-clés de produit
  const productKeywords = [
    'téléphone', 'telephone', 'smartphone', 'mobile',
    'ordinateur', 'laptop', 'pc', 'computer',
    'tablette', 'tablet', 'ipad',
    'télévision', 'television', 'tv', 'écran',
    'casque', 'écouteurs', 'earbuds', 'airpods',
    'appareil photo', 'camera', 'caméra',
    'montre', 'watch', 'smartwatch',
    'imprimante', 'printer',
    'frigo', 'réfrigérateur', 'refrigerateur',
    'climatiseur', 'clim',
    'machine à laver', 'lave-linge',
    'micro-onde', 'microwave',
    'ventilateur', 'fan',
    'samsung', 'iphone', 'apple', 'xiaomi', 'huawei',
  ]

  for (const keyword of productKeywords) {
    if (message.toLowerCase().includes(keyword)) {
      params.search = keyword
      break
    }
  }

  // Si pas de mot-clé trouvé, utiliser une partie du message
  if (!params.search) {
    // Extraire les mots significatifs (plus de 3 caractères)
    const words = message
      .toLowerCase()
      .split(/\s+/)
      .filter(w => w.length > 3 && !['pour', 'avec', 'dans', 'quel', 'quelle', 'voudrais', 'cherche', 'besoin'].includes(w))

    if (words.length > 0) {
      params.search = words[0]
    }
  }

  return params
}

/**
 * Récupère les produits depuis le nouveau service /api/v1/products/
 * Ce service ne nécessite pas d'authentification
 */
async function fetchProducts(
  apiBaseUrl: string,
  params: { search?: string; minPrice?: number; maxPrice?: number }
): Promise<Product[]> {
  try {
    const queryParams = new URLSearchParams()
    queryParams.append('page', '1')
    queryParams.append('page_size', '5')

    if (params.search) {
      queryParams.append('search', params.search)
    }
    if (params.minPrice) {
      queryParams.append('min_price', params.minPrice.toString())
    }
    if (params.maxPrice) {
      queryParams.append('max_price', params.maxPrice.toString())
    }

    const url = `${apiBaseUrl}/api/v1/products/?${queryParams}`

    // Utilisation du nouveau endpoint /api/v1/products/ (sans authentification requise)
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      console.error('Erreur API Products:', response.status, await response.text())
      return []
    }

    const data: ProductListResponse = await response.json()
    return data.items || []
  } catch (error) {
    console.error('Erreur lors de la récupération des produits:', error)
    return []
  }
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()

  // Lire le corps de la requête
  const body = await readBody<ChatRequest>(event)

  if (!body.message && (!body.images || body.images.length === 0)) {
    throw createError({
      statusCode: 400,
      message: 'Le message ou au moins une image est requis'
    })
  }

  try {
    // 1. Construire le contenu de la requête (parts)
    const parts: any[] = [{ text: SYSTEM_PROMPT + '\n\n' }]

    // Ajouter l'historique de conversation (limité)
    if (body.history && body.history.length > 0) {
      const historyText = body.history
        .map(msg => `${msg.role === 'user' ? 'Client' : 'Telia'}: ${msg.content}`)
        .join('\n')
      parts.push({ text: `Historique de la conversation:\n${historyText}\n\n` })
    }

    // Ajouter les images si présentes
    if (body.images && body.images.length > 0) {
      for (const img of body.images) {
        // Extraire les données base64 de l'image
        let imageData = img.data
        let mimeType = img.mimeType

        if (imageData.startsWith('data:')) {
          // Format: data:image/jpeg;base64,/9j/4AAQ...
          const matches = imageData.match(/^data:([^;]+);base64,(.+)$/)
          if (matches) {
            mimeType = matches[1]
            imageData = matches[2]
          }
        }

        parts.push({
          inlineData: {
            mimeType: mimeType || 'image/jpeg',
            data: imageData
          }
        })
      }
    }

    // Ajouter le message utilisateur
    parts.push({ text: `\nNouvelle requête du client: ${body.message || 'Analyse cette image et propose-moi des produits similaires.'}` })


    // --- APPEL API DIRECT (Bypass SDK pour support modèle Preview & Tools) ---

    // Préparation des contenus pour l'API REST
    const apiContents = [
      {
        role: 'user',
        parts: parts
      }
    ]

    // Utilisation de gemini-flash-latest comme demandé
    const modelName = 'gemini-flash-latest'
    const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${config.geminiApiKey}`

    const apiResponse = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        contents: apiContents,
        // Outils : Google Search
        tools: [
          { googleSearch: {} }
        ],
        // Configuration de la génération
        generationConfig: {
          temperature: 0.7,
          topK: 40,
          topP: 0.95,
          maxOutputTokens: 8192,
          // Configuration expérimentale Thinking (si supporté par le modèle)
          thinkingConfig: {
            includeThoughts: false // On cache les "pensées" internes pour l'utilisateur final
          }
        }
      })
    })

    if (!apiResponse.ok) {
      const errorText = await apiResponse.text()
      console.error('Erreur API Gemini Directe:', apiResponse.status, errorText)
      throw new Error(`Erreur API Google (${apiResponse.status}): ${errorText}`)
    }

    const result = await apiResponse.json()

    // Extraction du texte de la réponse (format REST)
    let textResponse = ''
    if (result.candidates && result.candidates.length > 0 && result.candidates[0].content && result.candidates[0].content.parts) {
      textResponse = result.candidates[0].content.parts.map((p: any) => p.text).join('')

      // Si des résultats de grounding Google Search sont utilisés, on peut l'indiquer si nécessaire
      if (result.candidates[0].groundingMetadata) {
        // Log pour info server
        console.log('Grounding Metadata:', result.candidates[0].groundingMetadata)
      }
    } else {
      textResponse = "Désolé, je n'ai pas pu générer de réponse."
    }

    // Extraire les paramètres de recherche pour les produits
    const searchParams = extractSearchParams(body.message || '')

    // Récupérer les produits correspondants depuis le nouveau service
    // Le service /api/v1/products/ ne nécessite pas d'authentification
    let products: Product[] = []

    if (searchParams.search || searchParams.maxPrice) {
      products = await fetchProducts(
        config.public.apiBaseUrl as string,
        searchParams
      )
    }

    return {
      content: textResponse,
      products: products.length > 0 ? products : undefined
    }

  } catch (error: any) {
    console.error('============ ERREUR GEMINI DETAIL ===========')
    console.error('Message:', error.message)
    console.error('Cause:', error.cause)
    console.error('Stack:', error.stack)
    if (error.response) {
      console.error('API Response:', JSON.stringify(error.response, null, 2))
    }
    console.error('=============================================')

    throw createError({
      statusCode: 500,
      message: `Erreur interne: ${error.message || 'Erreur inconnue'}`
    })
  }
})


