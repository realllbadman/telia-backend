<template>
  <section>
    <div v-if="loading" class="grid">
      <article v-for="n in 6" :key="`s-${n}`" class="card skeleton">
        <div class="bar w60"></div>
        <div class="bar w90"></div>
        <div class="bar w70"></div>
        <div class="bar w45"></div>
      </article>
    </div>

    <div v-else-if="!products.length" class="empty">
      <h3>No recommendations yet</h3>
      <p>Run a text search, upload an image or video, or record audio to see matching products.</p>
    </div>

    <div v-else class="grid">
      <article v-for="item in products" :key="item.id || item.sku" class="card">
        <div class="card-top">
          <h3>{{ item.name || 'Unnamed product' }}</h3>
          <span class="sku">{{ item.sku || 'N/A' }}</span>
        </div>

        <p class="price">{{ formatPrice(item.price) }}</p>

        <div v-if="hasRelevance(item)" class="relevance">
          <span>Relevance</span>
          <div class="meter">
            <div class="fill" :style="{ width: `${relevancePercent(item.relevance_score)}%` }"></div>
          </div>
          <strong>{{ Number(item.relevance_score).toFixed(2) }}</strong>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  products: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  language: {
    type: String,
    default: 'en'
  }
})

const hasRelevance = (item) => item.relevance_score !== null && item.relevance_score !== undefined

const relevancePercent = (score) => {
  const numeric = Number(score)
  if (Number.isNaN(numeric)) return 0
  const clamped = Math.max(0, Math.min(1, numeric))
  return Math.round(clamped * 100)
}

const formatPrice = (value) => {
  const numeric = Number(value)
  if (value === null || value === undefined || Number.isNaN(numeric)) return '-'

  const locale = props.language === 'fr' ? 'fr-FR' : 'en-US'
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'XAF',
    maximumFractionDigits: 0
  }).format(numeric)
}
</script>

<style scoped>
.empty {
  border: 1px dashed #33475f;
  border-radius: 14px;
  padding: 1.3rem;
  text-align: center;
  color: #99afc7;
  background: #0d1728;
}

.empty h3 {
  margin: 0;
  color: #e8f0fb;
}

.empty p {
  margin: 0.45rem 0 0;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1rem;
}

.card {
  border: 1px solid #293a53;
  border-radius: 14px;
  padding: 1rem;
  background: linear-gradient(180deg, #0d1728 0%, #111d31 100%);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.38);
}

.card-top {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

h3 {
  margin: 0;
  font-size: 1rem;
  color: #e8f0fb;
}

.sku {
  color: #99afc7;
  font-size: 0.85rem;
  font-weight: 600;
}

.price {
  margin: 0.85rem 0;
  font-size: 1.12rem;
  font-weight: 700;
  color: #5eead4;
}

.relevance {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 0.45rem;
  color: #bfdbfe;
  font-size: 0.82rem;
}

.meter {
  height: 8px;
  border-radius: 999px;
  background: #1e3a5f;
  overflow: hidden;
}

.fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb 0%, #06b6d4 100%);
}

.skeleton .bar {
  height: 12px;
  border-radius: 999px;
  background: linear-gradient(90deg, #1b2a3d 25%, #2a3f58 50%, #1b2a3d 75%);
  background-size: 220% 100%;
  animation: shimmer 1.2s infinite;
  margin: 0.55rem 0;
}

.skeleton .w60 { width: 60%; }
.skeleton .w90 { width: 90%; }
.skeleton .w70 { width: 70%; }
.skeleton .w45 { width: 45%; }

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
