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

// Interface pour un produit
interface Product {
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

/**
 * Prompt système pour Telia Assistant
 */
const SYSTEM_PROMPT = `Tu es Telia Assistant, l'assistant shopping intelligent de Glotelho, une plateforme e-commerce camerounaise.

Ton rôle est d'aider les clients à :
1. Trouver des produits adaptés à leurs besoins et budget
2. Analyser des images de produits pour suggérer des alternatives
3. Comparer les prix et caractéristiques
4. Passer des commandes
5. Suivre leurs commandes

Règles importantes :
- Réponds TOUJOURS en français
- Sois amical, professionnel et concis
- Utilise des emojis modérément pour rendre les réponses plus engageantes
- Quand un utilisateur demande des produits, analyse sa requête pour extraire :
  * La catégorie de produit (téléphone, ordinateur, électroménager, etc.)
  * Le budget maximum (si mentionné)
  * Les caractéristiques souhaitées
  * Le profil utilisateur (photographe, gamer, professionnel, etc.)
- Propose toujours 5 produits maximum
- Indique clairement les prix en FCFA (XAF)
- Pour les commandes, guide l'utilisateur vers le processus d'achat sur glotelho.cm

Si un utilisateur envoie une image :
- Analyse l'image pour identifier le type de produit
- Propose des produits similaires disponibles sur Glotelho
- Mentionne les caractéristiques que tu as identifiées

Format de réponse pour les recommandations de produits :
Utilise un format clair avec le nom, prix et brève description.

Tu as accès à la base de produits de Glotelho via l'API backend.`

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
        // Ajouter une marge de 20% pour le prix min
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
 * Récupère les produits depuis l'API backend
 */
async function fetchProducts(
  apiBaseUrl: string,
  token: string,
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

    const response = await fetch(`${apiBaseUrl}/magento/products?${queryParams}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      console.error('Erreur API Magento:', response.status, await response.text())
      return []
    }

    const data = await response.json()
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
    // Initialiser le client Gemini
    const genAI = new GoogleGenerativeAI(config.geminiApiKey)
    const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' })

    // Construire le contenu de la requête
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

    // Générer la réponse avec Gemini
    const result = await model.generateContent(parts)
    const response = result.response
    let textResponse = response.text()

    // Extraire les paramètres de recherche pour les produits
    const searchParams = extractSearchParams(body.message || '')

    // Variable pour stocker les produits (optionnel - à activer si le backend est disponible)
    let products: Product[] = []

    // Note: Décommenter ces lignes si vous avez un token d'accès admin
    // et que vous voulez récupérer les produits depuis le backend
    /*
    if (searchParams.search || searchParams.maxPrice) {
      products = await fetchProducts(
        config.public.apiBaseUrl as string,
        'VOTRE_TOKEN_ADMIN',
        searchParams
      )
    }
    */

    return {
      content: textResponse,
      products: products.length > 0 ? products : undefined
    }

  } catch (error: any) {
    console.error('Erreur Gemini:', error)

    throw createError({
      statusCode: 500,
      message: error.message || 'Erreur lors du traitement de votre demande'
    })
  }
})


