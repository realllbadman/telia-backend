<template>
  <section class="product-section">

    <!-- ── Loading skeletons ──────────────────────────────────────────────── -->
    <template v-if="loading">
      <div v-for="row in 2" :key="`row-${row}`" class="group-section">
        <div class="group-header skeleton-header">
          <span class="skeleton-pill w40"></span>
          <span class="skeleton-pill w15"></span>
        </div>
        <div class="carousel">
          <div v-for="n in 6" :key="`sk-${row}-${n}`" class="card skeleton">
            <div class="card-image skeleton-img"></div>
            <div class="card-body">
              <div class="sk-bar w80"></div>
              <div class="sk-bar w55"></div>
              <div class="sk-bar w40 price-bar"></div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ── Empty state ────────────────────────────────────────────────────── -->
    <div v-else-if="!hasContent" class="empty">
      <div class="empty-icon">🔍</div>
      <h3>No recommendations yet</h3>
      <p>Search by text, image, video, or audio to see matching products.</p>
    </div>

    <!-- ── Grouped carousel mode (image + text multi-intent) ─────────────── -->
    <template v-else-if="groups.length > 1">
      <div
        v-for="(group, gi) in groups"
        :key="group.category"
        class="group-section"
      >
        <!-- Category header row -->
        <div class="group-header">
          <h2 class="group-title">
            <span class="title-accent"></span>
            {{ capitalise(group.category) }}
            <span class="count-badge">{{ group.products.length }}</span>
          </h2>
          <button class="view-all" @click="openViewAll(group)">
            View all <span aria-hidden="true">→</span>
          </button>
        </div>

        <!-- Scroll row with arrow navigation -->
        <div class="carousel-wrap">
          <button
            class="arrow arrow-left"
            :aria-label="`Scroll ${group.category} left`"
            @click="scroll(gi, -1)"
          >‹</button>

          <div
            :ref="el => { if (el) carouselRefs[gi] = el }"
            class="carousel"
            :aria-label="`${group.category} products`"
          >
            <article
              v-for="item in group.products"
              :key="item.id || item.sku"
              class="card"
              @click="openProduct(item)"
            >
              <!-- Product image -->
              <div class="card-image">
                <img
                  v-if="item.image_url"
                  :src="item.image_url"
                  :alt="item.name || 'Product'"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="img-placeholder">
                  <span>No image</span>
                </div>
              </div>

              <!-- Product info -->
              <div class="card-body">
                <p class="product-name" :title="item.name">{{ item.name || 'Unnamed product' }}</p>
                <p class="product-sku">{{ item.sku || '' }}</p>
                <p class="product-price">{{ formatPrice(item.price) }}</p>

                <!-- Quick action -->
                <button class="btn-view" @click.stop="openProduct(item)">
                  View
                </button>
              </div>
            </article>
          </div>

          <button
            class="arrow arrow-right"
            :aria-label="`Scroll ${group.category} right`"
            @click="scroll(gi, 1)"
          >›</button>
        </div>
      </div>
    </template>

    <!-- ── Normal grid mode (single category / text-only / image-only) ───── -->
    <template v-else>
      <!-- Exact matches -->
      <div v-if="exactMatches.length" class="grid">
        <article
          v-for="item in exactMatches"
          :key="item.id || item.sku"
          class="card grid-card"
          @click="openProduct(item)"
        >
          <div class="card-image">
            <img
              v-if="item.image_url"
              :src="item.image_url"
              :alt="item.name || 'Product'"
              loading="lazy"
              decoding="async"
            />
            <div v-else class="img-placeholder"><span>No image</span></div>
          </div>
          <div class="card-body">
            <p class="product-name" :title="item.name">{{ item.name || 'Unnamed product' }}</p>
            <p class="product-sku">{{ item.sku || '' }}</p>
            <p class="product-price">{{ formatPrice(item.price) }}</p>
            <div v-if="hasRelevance(item)" class="relevance">
              <div class="meter">
                <div class="fill" :style="{ width: `${relevancePercent(item.relevance_score)}%` }"></div>
              </div>
              <span class="score">{{ Number(item.relevance_score).toFixed(1) }}</span>
            </div>
            <button class="btn-view" @click.stop="openProduct(item)">View</button>
          </div>
        </article>
      </div>

      <!-- Suggestions -->
      <template v-if="suggestions.length">
        <p class="section-label">
          {{ language === 'fr' ? 'Vous pourriez aussi aimer' : 'You may also like' }}
        </p>
        <div class="grid">
          <article
            v-for="item in suggestions"
            :key="item.id || item.sku"
            class="card grid-card suggestion"
            @click="openProduct(item)"
          >
            <div class="card-image">
              <img
                v-if="item.image_url"
                :src="item.image_url"
                :alt="item.name || 'Product'"
                loading="lazy"
                decoding="async"
              />
              <div v-else class="img-placeholder"><span>No image</span></div>
            </div>
            <div class="card-body">
              <p class="product-name" :title="item.name">{{ item.name || 'Unnamed product' }}</p>
              <p class="product-sku">{{ item.sku || '' }}</p>
              <p class="product-price">{{ formatPrice(item.price) }}</p>
            </div>
          </article>
        </div>
      </template>
    </template>

    <!-- ── Modals (Teleported to <body>, no z-index conflict) ──────────────── -->
    <ProductDetailModal
      v-if="selectedProduct"
      :product="selectedProduct"
      :language="language"
      @close="closeProduct"
    />

    <CategoryViewAllModal
      v-if="selectedGroup"
      :group="selectedGroup"
      :language="language"
      @close="closeViewAll"
      @product-click="openProductFromViewAll"
    />

  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  products: { type: Array, default: () => [] },
  groups:   { type: Array, default: () => [] },   // [{ category, products[] }]
  loading:  { type: Boolean, default: false },
  language: { type: String, default: 'en' },
})

// Parent can still listen to these if needed for routing/analytics
const emit = defineEmits(['product-click', 'view-all'])

// ── Modal state ───────────────────────────────────────────────────────────
// Handled internally so the feature works without parent changes.
const selectedProduct  = ref(null)   // opens ProductDetailModal
const selectedGroup    = ref(null)   // opens CategoryViewAllModal

function openProduct(item) {
  selectedProduct.value = item
}
function closeProduct() {
  selectedProduct.value = null
}
function openViewAll(group) {
  selectedGroup.value = group
}
function closeViewAll() {
  selectedGroup.value = null
}
// When a card in the View-All modal is clicked, open the detail modal on top
function openProductFromViewAll(item) {
  selectedProduct.value = item
}

// Close both modals on Escape
function onKeydown(e) {
  if (e.key !== 'Escape') return
  if (selectedProduct.value) { closeProduct(); return }
  if (selectedGroup.value)   { closeViewAll() }
}
onMounted(()          => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(()    => window.removeEventListener('keydown', onKeydown))

// ── Carousel scroll refs (one per group row) ──────────────────────────────
const carouselRefs = ref([])

const CARD_WIDTH = 204   // card width (180) + gap (1rem ≈ 16px) + a little margin

function scroll(groupIndex, direction) {
  const el = carouselRefs.value[groupIndex]
  if (!el) return
  el.scrollBy({ left: direction * CARD_WIDTH * 3, behavior: 'smooth' })
}

// ── Grid mode helpers ─────────────────────────────────────────────────────
const hasContent = computed(() => props.groups.length > 0 || props.products.length > 0)

const exactMatches = computed(() =>
  props.products.filter(p => p.relevance_score !== null && p.relevance_score !== undefined)
)
const suggestions = computed(() =>
  props.products.filter(p => p.relevance_score === null || p.relevance_score === undefined)
)
const maxScore = computed(() => {
  const scores = exactMatches.value.map(p => Number(p.relevance_score)).filter(n => !isNaN(n))
  return scores.length ? Math.max(...scores) : 1
})
const hasRelevance   = (item) => item.relevance_score !== null && item.relevance_score !== undefined
const relevancePercent = (score) => {
  const n = Number(score)
  return isNaN(n) ? 0 : Math.round(Math.min(100, (n / (maxScore.value || 1)) * 100))
}

// ── Shared helpers ────────────────────────────────────────────────────────
const capitalise = (str) => str ? str.charAt(0).toUpperCase() + str.slice(1) : ''

const formatPrice = (value) => {
  const numeric = Number(value)
  if (value === null || value === undefined || Number.isNaN(numeric)) return '—'
  return new Intl.NumberFormat(props.language === 'fr' ? 'fr-FR' : 'en-US', {
    style: 'currency',
    currency: 'XAF',
    maximumFractionDigits: 0,
  }).format(numeric)
}
</script>

<style scoped>
/* ── Layout ───────────────────────────────────────────────────────────────── */
.product-section {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

/* ── Empty state ──────────────────────────────────────────────────────────── */
.empty {
  border: 1px dashed #33475f;
  border-radius: 16px;
  padding: 2.5rem 1.5rem;
  text-align: center;
  color: #99afc7;
  background: #0d1728;
}
.empty-icon { font-size: 2rem; margin-bottom: 0.5rem; }
.empty h3   { margin: 0; color: #e8f0fb; font-size: 1.1rem; }
.empty p    { margin: 0.4rem 0 0; font-size: 0.92rem; }

/* ── Category section ─────────────────────────────────────────────────────── */
.group-section { margin-bottom: 1.5rem; }

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.7rem;
  padding: 0 0.25rem;
}

.group-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #e8f0fb;
}

.title-accent {
  display: inline-block;
  width: 3px;
  height: 1em;
  border-radius: 2px;
  background: linear-gradient(180deg, #0ea5a4, #2563eb);
  flex-shrink: 0;
}

.count-badge {
  background: #0f2c35;
  color: #5eead4;
  border: 1px solid #115e59;
  border-radius: 999px;
  font-size: 0.72rem;
  padding: 0.05rem 0.45rem;
  font-weight: 600;
  letter-spacing: 0;
}

.view-all {
  background: none;
  border: 1px solid #293a53;
  border-radius: 999px;
  color: #67e8f9;
  font-size: 0.8rem;
  padding: 0.25rem 0.75rem;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.15s, color 0.15s;
}
.view-all:hover {
  border-color: #0ea5a4;
  color: #a5f3fc;
}

/* ── Carousel wrapper + arrows ────────────────────────────────────────────── */
.carousel-wrap {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.arrow {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid #293a53;
  background: #0d1728;
  color: #94a3b8;
  font-size: 1.2rem;
  line-height: 1;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  z-index: 1;
}
.arrow:hover {
  background: #0f2c35;
  border-color: #0ea5a4;
  color: #5eead4;
}

/* Hide arrows on mobile — touch swipe is enough */
@media (max-width: 640px) {
  .arrow { display: none; }
}

/* ── Carousel strip ───────────────────────────────────────────────────────── */
.carousel {
  display: flex;
  gap: 0.75rem;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  padding: 0.25rem 0.25rem 0.75rem;

  /* Hide scrollbar visually but keep functionality */
  scrollbar-width: none;          /* Firefox */
  -ms-overflow-style: none;       /* IE/Edge */
}
.carousel::-webkit-scrollbar { display: none; }  /* Chrome/Safari */

/* ── Product card (carousel) ──────────────────────────────────────────────── */
.card {
  flex: 0 0 180px;               /* fixed width — never stretches */
  scroll-snap-align: start;
  border: 1px solid #1e2d42;
  border-radius: 12px;
  background: linear-gradient(160deg, #0d1728 0%, #0f1d35 100%);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.card:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.45);
  border-color: #0ea5a4;
}

/* ── Card image ───────────────────────────────────────────────────────────── */
.card-image {
  width: 100%;
  aspect-ratio: 1 / 1;           /* perfect square */
  background: #0b1220;
  display: grid;
  place-items: center;
  overflow: hidden;
}
.card-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;           /* show full product, no crop */
  display: block;
  transition: transform 0.22s ease;
}
.card:hover .card-image img {
  transform: scale(1.06);
}
.img-placeholder {
  color: #475569;
  font-size: 0.78rem;
  text-align: center;
}

/* ── Card body ────────────────────────────────────────────────────────────── */
.card-body {
  padding: 0.6rem 0.65rem 0.65rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.product-name {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 600;
  color: #dbe7f3;
  /* Clamp to 2 lines */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.35;
  min-height: 2.2em;   /* keeps cards same height even with short names */
}

.product-sku {
  margin: 0;
  font-size: 0.72rem;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.product-price {
  margin: 0.3rem 0 0.4rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: #5eead4;
}

/* Quick action button */
.btn-view {
  width: 100%;
  padding: 0.35rem 0;
  border-radius: 6px;
  border: 1px solid #164e63;
  background: transparent;
  color: #67e8f9;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.14s, border-color 0.14s;
}
.btn-view:hover {
  background: #082f49;
  border-color: #0ea5a4;
}

/* ── Normal grid mode ─────────────────────────────────────────────────────── */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.85rem;
}

.grid-card {
  flex: unset;                    /* override carousel flex-shrink:0 */
  scroll-snap-align: unset;
}

/* Relevance bar (grid mode only) */
.relevance {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.2rem;
}
.meter {
  flex: 1;
  height: 5px;
  border-radius: 999px;
  background: #1e3a5f;
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #06b6d4);
}
.score {
  font-size: 0.72rem;
  color: #93c5fd;
  white-space: nowrap;
}

/* Suggestion cards are slightly dimmed */
.suggestion {
  opacity: 0.75;
}
.suggestion:hover {
  opacity: 1;
}

.section-label {
  margin: 1.2rem 0 0.55rem;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #64748b;
}

/* ── Skeleton loaders ─────────────────────────────────────────────────────── */
.skeleton {
  pointer-events: none;
}
.skeleton-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.skeleton-pill {
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(90deg, #1b2a3d 25%, #2a3f58 50%, #1b2a3d 75%);
  background-size: 220% 100%;
  animation: shimmer 1.3s infinite;
  display: inline-block;
}
.skeleton-img {
  aspect-ratio: 1 / 1;
  background: linear-gradient(90deg, #1b2a3d 25%, #2a3f58 50%, #1b2a3d 75%);
  background-size: 220% 100%;
  animation: shimmer 1.3s infinite;
}
.sk-bar {
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, #1b2a3d 25%, #2a3f58 50%, #1b2a3d 75%);
  background-size: 220% 100%;
  animation: shimmer 1.3s infinite;
  margin: 0.3rem 0;
}
.price-bar { margin-top: 0.5rem; }

/* Width helpers */
.w80 { width: 80%; }
.w55 { width: 55%; }
.w40 { width: 40%; }
.w15 { width: 15%; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Responsive card visibility ───────────────────────────────────────────── */
/* Desktop: ~5-6 cards visible (180px × 6 = 1080px, fits most screens) */
/* Tablet:  ~3-4 cards naturally visible */
/* Mobile:  ~2.5 cards — partial 3rd card peeks to signal scroll */

@media (max-width: 480px) {
  .card { flex: 0 0 150px; }

  /* Make the partial-card peek effect obvious on small screens */
  .carousel { padding-right: 2.5rem; }
}

@media (min-width: 481px) and (max-width: 768px) {
  .card { flex: 0 0 165px; }
}
</style>
