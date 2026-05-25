<template>
  <Teleport to="body">
    <div class="overlay" @click.self="$emit('close')" role="dialog" aria-modal="true" :aria-label="product.name">

      <div class="modal">
        <!-- Close -->
        <button class="close-btn" aria-label="Close" @click="$emit('close')">✕</button>

        <div class="modal-body">
          <!-- Image panel -->
          <div class="img-panel">
            <img
              v-if="product.image_url"
              :src="product.image_url"
              :alt="product.name"
              class="product-img"
            />
            <div v-else class="img-placeholder">No image available</div>
          </div>

          <!-- Info panel -->
          <div class="info-panel">
            <p class="product-sku">SKU: {{ product.sku }}</p>
            <h2 class="product-name">{{ product.name }}</h2>
            <p class="product-price">{{ formatPrice(product.price) }}</p>

            <div v-if="product.caption" class="description-block">
              <p class="desc-label">{{ language === 'fr' ? 'Caractéristiques' : 'Key Features' }}</p>
              <p class="desc-text">{{ product.caption }}</p>
            </div>

            <div v-if="hasRelevance" class="relevance-block">
              <p class="desc-label">Relevance</p>
              <div class="meter-wrap">
                <div class="meter">
                  <div class="fill" :style="{ width: relevancePct + '%' }"></div>
                </div>
                <span class="score">{{ Number(product.relevance_score).toFixed(2) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  product: { type: Object, required: true },
  language: { type: String, default: 'en' },
})

defineEmits(['close'])

const hasRelevance = computed(() =>
  props.product.relevance_score !== null && props.product.relevance_score !== undefined
)

const relevancePct = computed(() => {
  const n = Number(props.product.relevance_score)
  return isNaN(n) ? 0 : Math.min(100, Math.round(n * 10))   // rough normalisation
})

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
/* ── Overlay backdrop ─────────────────────────────────────────────────────── */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(4, 10, 20, 0.82);
  backdrop-filter: blur(4px);
  z-index: 999;
  display: grid;
  place-items: center;
  padding: 1rem;
  animation: fade-in 0.18s ease;
}

@keyframes fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* ── Modal card ───────────────────────────────────────────────────────────── */
.modal {
  position: relative;
  width: min(720px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  border-radius: 18px;
  background: linear-gradient(160deg, #0d1728 0%, #0f1d35 100%);
  border: 1px solid #1e3a5f;
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.6);
  animation: slide-up 0.2s ease;
}

@keyframes slide-up {
  from { transform: translateY(20px); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}

.close-btn {
  position: absolute;
  top: 0.85rem;
  right: 0.85rem;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid #293a53;
  background: #0b1220;
  color: #94a3b8;
  font-size: 1rem;
  cursor: pointer;
  display: grid;
  place-items: center;
  z-index: 1;
  transition: border-color 0.15s, color 0.15s;
}
.close-btn:hover { border-color: #0ea5a4; color: #5eead4; }

/* ── Modal body ───────────────────────────────────────────────────────────── */
.modal-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  padding: 1.5rem;
}

@media (max-width: 540px) {
  .modal-body { grid-template-columns: 1fr; }
}

/* ── Image panel ──────────────────────────────────────────────────────────── */
.img-panel {
  border-radius: 12px;
  overflow: hidden;
  background: #0b1220;
  border: 1px solid #1e2d42;
  display: grid;
  place-items: center;
  aspect-ratio: 1 / 1;
}

.product-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.img-placeholder {
  color: #475569;
  font-size: 0.9rem;
}

/* ── Info panel ───────────────────────────────────────────────────────────── */
.info-panel {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  padding-top: 0.25rem;
}

.product-sku {
  margin: 0;
  font-size: 0.78rem;
  color: #64748b;
  font-family: monospace;
}

.product-name {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #e8f0fb;
  line-height: 1.35;
}

.product-price {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 800;
  color: #5eead4;
}

/* ── Description block ────────────────────────────────────────────────────── */
.description-block {
  border-top: 1px solid #1e3a5f;
  padding-top: 0.75rem;
}

.desc-label {
  margin: 0 0 0.35rem;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #5eead4;
}

.desc-text {
  margin: 0;
  font-size: 0.9rem;
  color: #9ab0c8;
  line-height: 1.6;
}

/* ── Relevance ────────────────────────────────────────────────────────────── */
.relevance-block {
  border-top: 1px solid #1e3a5f;
  padding-top: 0.75rem;
}

.meter-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.meter {
  flex: 1;
  height: 7px;
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
  font-size: 0.78rem;
  color: #93c5fd;
  white-space: nowrap;
}
</style>
