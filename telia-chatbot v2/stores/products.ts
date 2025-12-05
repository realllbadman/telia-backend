/**
 * Store Pinia pour la gestion des produits
 * 
 * Ce store gère l'accès aux produits via le nouveau service Magento
 * exposé sur /api/v1/products/
 */

import { defineStore } from 'pinia'

// Interface pour les informations de prix (correspond à ProductPrice du backend)
export interface ProductPrice {
    amount: number
    regular_amount: number | null
    special_amount: number | null
    currency: string
    formatted_price: string | null
    formatted_regular_price: string | null
    discount_percentage: number | null
    has_discount: boolean
}

// Interface pour une image produit (correspond à ProductImage du backend)
export interface ProductImage {
    url: string
    label: string | null
    type: string | null
    position: number | null
    is_main: boolean
    width: number | null
    height: number | null
}

// Interface pour une caractéristique produit (correspond à ProductCharacteristic du backend)
export interface ProductCharacteristic {
    code: string
    label: string
    value: any
    value_label: string | null
}

// Interface pour un produit complet (correspond à ProductInfo du backend)
export interface Product {
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
    stock_quantity: number | null
    price: ProductPrice
    images: ProductImage[]
    main_image: ProductImage | null
    characteristics: ProductCharacteristic[]
    categories: string[]
    brand: string | null
    store_id: number
    created_at: string | null
    updated_at: string | null
}

// Interface pour la réponse paginée (correspond à ProductListResponse du backend)
export interface ProductListResponse {
    items: Product[]
    total_count: number
    page: number
    page_size: number
    has_next: boolean
    has_previous: boolean
    total_pages: number
}

// Interface pour les filtres de recherche
export interface ProductSearchFilters {
    search?: string
    min_price?: number
    max_price?: number
    category_id?: number
    page?: number
    page_size?: number
}

// Interface pour l'état du store
interface ProductState {
    products: Product[]
    currentProduct: Product | null
    totalCount: number
    page: number
    pageSize: number
    hasNext: boolean
    hasPrevious: boolean
    totalPages: number
    isLoading: boolean
    error: string | null
    lastSearch: string | null
}

export const useProductStore = defineStore('products', {
    /**
     * État initial du store de produits
     */
    state: (): ProductState => ({
        products: [],
        currentProduct: null,
        totalCount: 0,
        page: 1,
        pageSize: 10,
        hasNext: false,
        hasPrevious: false,
        totalPages: 1,
        isLoading: false,
        error: null,
        lastSearch: null
    }),

    /**
     * Getters pour accéder aux données calculées
     */
    getters: {
        // Vérifie si des produits sont chargés
        hasProducts: (state): boolean => state.products.length > 0,

        // Récupère le nombre de produits
        productCount: (state): number => state.products.length,

        // Récupère les produits en promotion
        productsOnSale: (state): Product[] =>
            state.products.filter(p => p.price.has_discount),

        // Récupère les produits disponibles
        availableProducts: (state): Product[] =>
            state.products.filter(p => p.is_available)
    },

    /**
     * Actions pour modifier l'état
     */
    actions: {
        /**
         * Récupérer la liste des produits depuis le nouveau service
         * 
         * @param filters - Filtres de recherche optionnels
         * @returns Promise<ProductListResponse>
         */
        async fetchProducts(filters: ProductSearchFilters = {}): Promise<ProductListResponse | null> {
            const config = useRuntimeConfig()
            this.isLoading = true
            this.error = null

            try {
                // Construction des paramètres de requête
                const queryParams = new URLSearchParams()

                queryParams.append('page', String(filters.page || 1))
                queryParams.append('page_size', String(filters.page_size || 10))

                if (filters.search) {
                    queryParams.append('search', filters.search)
                    this.lastSearch = filters.search
                }
                if (filters.min_price !== undefined) {
                    queryParams.append('min_price', String(filters.min_price))
                }
                if (filters.max_price !== undefined) {
                    queryParams.append('max_price', String(filters.max_price))
                }
                if (filters.category_id !== undefined) {
                    queryParams.append('category_id', String(filters.category_id))
                }

                // Appel à la nouvelle API /api/v1/products/
                const response = await $fetch<ProductListResponse>(
                    `${config.public.apiBaseUrl}/api/v1/products/?${queryParams}`
                )

                // Mise à jour de l'état
                this.products = response.items
                this.totalCount = response.total_count
                this.page = response.page
                this.pageSize = response.page_size
                this.hasNext = response.has_next
                this.hasPrevious = response.has_previous
                this.totalPages = response.total_pages

                return response
            } catch (error: any) {
                this.error = error?.data?.message || 'Erreur lors de la récupération des produits'
                console.error('Erreur fetchProducts:', error)
                return null
            } finally {
                this.isLoading = false
            }
        },

        /**
         * Rechercher des produits par terme de recherche
         * 
         * @param query - Terme de recherche
         * @param pageSize - Nombre de résultats (défaut: 5)
         */
        async searchProducts(query: string, pageSize: number = 5): Promise<Product[]> {
            const config = useRuntimeConfig()
            this.isLoading = true
            this.error = null

            try {
                const response = await $fetch<ProductListResponse>(
                    `${config.public.apiBaseUrl}/api/v1/products/search?q=${encodeURIComponent(query)}&page_size=${pageSize}`
                )

                this.products = response.items
                this.lastSearch = query
                return response.items
            } catch (error: any) {
                this.error = error?.data?.message || 'Erreur lors de la recherche'
                console.error('Erreur searchProducts:', error)
                return []
            } finally {
                this.isLoading = false
            }
        },

        /**
         * Récupérer un produit par son ID
         * 
         * @param productId - ID du produit
         */
        async fetchProductById(productId: number): Promise<Product | null> {
            const config = useRuntimeConfig()
            this.isLoading = true
            this.error = null

            try {
                const product = await $fetch<Product>(
                    `${config.public.apiBaseUrl}/api/v1/products/${productId}`
                )

                this.currentProduct = product
                return product
            } catch (error: any) {
                this.error = error?.data?.message || 'Produit non trouvé'
                console.error('Erreur fetchProductById:', error)
                return null
            } finally {
                this.isLoading = false
            }
        },

        /**
         * Récupérer les produits par fourchette de prix
         * 
         * @param minPrice - Prix minimum
         * @param maxPrice - Prix maximum
         * @param pageSize - Nombre de résultats
         */
        async fetchProductsByPriceRange(
            minPrice: number,
            maxPrice: number,
            pageSize: number = 10
        ): Promise<Product[]> {
            const config = useRuntimeConfig()
            this.isLoading = true
            this.error = null

            try {
                const response = await $fetch<ProductListResponse>(
                    `${config.public.apiBaseUrl}/api/v1/products/price-range/?min_price=${minPrice}&max_price=${maxPrice}&page_size=${pageSize}`
                )

                this.products = response.items
                return response.items
            } catch (error: any) {
                this.error = error?.data?.message || 'Erreur lors du filtrage par prix'
                console.error('Erreur fetchProductsByPriceRange:', error)
                return []
            } finally {
                this.isLoading = false
            }
        },

        /**
         * Vérifier la connexion au service Magento
         */
        async checkHealth(): Promise<boolean> {
            const config = useRuntimeConfig()

            try {
                const response = await $fetch<{ status: string }>(
                    `${config.public.apiBaseUrl}/api/v1/products/health`
                )
                return response.status === 'connected'
            } catch (error) {
                console.error('Erreur health check:', error)
                return false
            }
        },

        /**
         * Réinitialiser l'état du store
         */
        resetState() {
            this.products = []
            this.currentProduct = null
            this.totalCount = 0
            this.page = 1
            this.hasNext = false
            this.hasPrevious = false
            this.totalPages = 1
            this.error = null
            this.lastSearch = null
        },

        /**
         * Charger la page suivante
         */
        async loadNextPage(): Promise<void> {
            if (this.hasNext) {
                await this.fetchProducts({
                    page: this.page + 1,
                    page_size: this.pageSize,
                    search: this.lastSearch || undefined
                })
            }
        },

        /**
         * Charger la page précédente
         */
        async loadPreviousPage(): Promise<void> {
            if (this.hasPrevious) {
                await this.fetchProducts({
                    page: this.page - 1,
                    page_size: this.pageSize,
                    search: this.lastSearch || undefined
                })
            }
        }
    }
})
