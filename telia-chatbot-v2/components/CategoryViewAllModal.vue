<template>
  <Teleport to="body">
    <div class="overlay" @click.self="$emit('close')" role="dialog" aria-modal="true">

      <div class="modal">
        <!-- Header -->
        <div class="modal-header">
          <div class="header-left">
            <span class="title-accent"></span>
            <h2 class="modal-title">{{ capitalise(group.category) }}</h2>
            <span class="count-badge">{{ group.products.length }} products</span>
          </div>
          <button class="close-btn" aria-label="Close" @click="$emit('close')">✕</button>
        </div>

        <!-- Products grid -->
        <div class="modal-body">
          <div class="grid">
            <article
              v-for="item in group.products"
              :key="item.id || item.sku"
              class="card"
              @click="$emit('product-click', item)"
            >
              <div class="card-image">
                <img
                  v-if="item.image_url"
                  :src="item.image_url"
                  :alt="item.name"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="img-placeholder">No image</div>
              </div>
              <div class="card-body">
                <p class="product-name" :title="item.name">{{ item.name || 'Unnamed product' }}</p>
                <p class="product-sku">{{ item.sku }}</p>
                <p class="product-price">{{ formatPrice(item.price) }}</p>
                <button class="btn-view" @click.stop="$emit('product-click', item)">View</button>
              </div>
            </article>
          </div>
        </div>
      </div>

    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  group:    { type: Object, required: true },  // { category, products[] }
  language: { type: String, default: 'en' },
})

defineEmits(['close', 'product-click'])

const capitalise = (str) => str ? str.charAt(0).toUpperCase() + str.slice(1) : ''

const formatPrice = (value) => {
  const numeric = Number(value)
  if (value === null || value === undefined || Number.isNaN(numeric)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'XAF',
    maximumFractionDigits: 0,
  }).format(numeric)
}
</script>

<style scoped>
/* ── Overlay ──────────────────────────────────────────────────────────────── */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(4, 10, 20, 0.85);
  backdrop-filter: blur(4px);
  z-index: 998;
  display: grid;
  place-items: start center;
  padding: 1rem;
  overflow-y: auto;
  animation: fade-in 0.18s ease;
}

@keyframes fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* ── Modal ────────────────────────────────────────────────────────────────── */
.modal {
  width: min(960px, 100%);
  margin: 2rem auto;
  border-radius: 18px;
  background: linear-gradient(160deg, #0d1728 0%, #0f1d35 100%);
  border: 1px solid #1e3a5f;
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.55);
  overflow: hidden;
  animation: slide-up 0.2s ease;
}

@keyframes slide-up {
  from { transform: translateY(16px); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}

/* ── Header ───────────────────────────────────────────────────────────────── */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #1e3a5f;
  background: #0b1220;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.title-accent {
  display: inline-block;
  width: 3px;
  height: 1.1em;
  border-radius: 2px;
  background: linear-gradient(180deg, #0ea5a4, #2563eb);
  flex-shrink: 0;
}

.modal-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #e8f0fb;
}

.count-badge {
  background: #0f2c35;
  color: #5eead4;
  border: 1px solid #115e59;
  border-radius: 999px;
  font-size: 0.72rem;
  padding: 0.1rem 0.5rem;
  font-weight: 600;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid #293a53;
  background: #0d1728;
  color: #94a3b8;
  font-size: 1rem;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: border-color 0.15s, color 0.15s;
  flex-shrink: 0;
}
.close-btn:hover { border-color: #0ea5a4; color: #5eead4; }

/* ── Body / grid ──────────────────────────────────────────────────────────── */
.modal-body {
  padding: 1.25rem;
  max-height: calc(90vh - 80px);
  overflow-y: auto;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(165px, 1fr));
  gap: 0.85rem;
}

/* ── Card ─────────────────────────────────────────────────────────────────── */
.card {
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

.card-image {
  width: 100%;
  aspect-ratio: 1 / 1;
  background: #0b1220;
  display: grid;
  place-items: center;
  overflow: hidden;
}
.card-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  transition: transform 0.22s ease;
}
.card:hover .card-image img { transform: scale(1.06); }

.img-placeholder { color: #475569; font-size: 0.78rem; }

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
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.35;
  min-height: 2.2em;
}
.product-sku   { margin: 0; font-size: 0.7rem; color: #64748b; }
.product-price { margin: 0.3rem 0 0.4rem; font-size: 0.95rem; font-weight: 700; color: #5eead4; }

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
.btn-view:hover { background: #082f49; border-color: #0ea5a4; }
</style>
