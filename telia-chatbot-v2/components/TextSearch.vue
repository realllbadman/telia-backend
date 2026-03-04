<template>
  <form class="search-card" @submit.prevent="onSubmit">
    <div class="card-header">
      <p class="eyebrow">Search by text</p>
      <h2>Describe what you need</h2>
      <p class="subtitle">Try keywords like product type, brand, or feature.</p>
    </div>

    <div class="input-wrap" :class="{ disabled: loading || disabled }">
      <input
        v-model="message"
        type="text"
        placeholder="e.g. fan, smart tv, gaming laptop"
        :disabled="loading || disabled"
        required
      />
      <button type="submit" :disabled="loading || disabled || !message.trim()">
        <span v-if="loading" class="spinner" aria-hidden="true"></span>
        {{ loading ? 'Searching' : 'Search' }}
      </button>
    </div>

    <div class="helper-row">
      <span class="language-pill">Language: {{ language.toUpperCase() }}</span>
      <div class="suggestions">
        <button type="button" :disabled="loading || disabled" @click="applySuggestion('fan')">Fan</button>
        <button type="button" :disabled="loading || disabled" @click="applySuggestion('fridge')">Fridge</button>
        <button type="button" :disabled="loading || disabled" @click="applySuggestion('smartphone')">Smartphone</button>
      </div>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  language: {
    type: String,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['search'])
const message = ref('')

const submit = (value) => {
  const text = value.trim()
  if (!text) return

  emit('search', {
    message: text,
    language: props.language
  })
}

const onSubmit = () => {
  submit(message.value)
}

const applySuggestion = (value) => {
  message.value = value
  submit(value)
}
</script>

<style scoped>
.search-card {
  border: 1px solid #293a53;
  border-radius: 16px;
  padding: 1rem;
  background: linear-gradient(180deg, #0d1728 0%, #111d31 100%);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.32);
}

.card-header {
  margin-bottom: 0.8rem;
}

.eyebrow {
  margin: 0 0 0.35rem;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #5eead4;
  font-weight: 700;
}

h2 {
  margin: 0;
  font-size: 1.18rem;
  color: #e8f0fb;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: #99afc7;
  font-size: 0.92rem;
}

.input-wrap {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.6rem;
}

.input-wrap.disabled {
  opacity: 0.75;
}

input {
  border: 1px solid #33475f;
  border-radius: 12px;
  padding: 0.78rem 0.9rem;
  font-size: 0.98rem;
  background: #0b1220;
  color: #e8f0fb;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

input::placeholder {
  color: #7d93aa;
}

input:focus {
  outline: none;
  border-color: #0ea5a4;
  box-shadow: 0 0 0 3px rgba(14, 165, 164, 0.22);
}

button {
  border: none;
  border-radius: 12px;
  padding: 0.78rem 1rem;
  background: linear-gradient(135deg, #0f766e 0%, #0891b2 100%);
  color: #fff;
  cursor: pointer;
  font-weight: 600;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 18px rgba(14, 116, 144, 0.25);
}

button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.helper-row {
  margin-top: 0.8rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.language-pill {
  background: #0f2c35;
  color: #99f6e4;
  border: 1px solid #115e59;
  border-radius: 999px;
  font-size: 0.78rem;
  padding: 0.25rem 0.6rem;
  font-weight: 600;
}

.suggestions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.suggestions button {
  background: #1e293b;
  color: #93c5fd;
  border: 1px solid #334155;
  border-radius: 999px;
  padding: 0.28rem 0.7rem;
  font-size: 0.8rem;
  box-shadow: none;
  transform: none;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: #ffffff;
  border-radius: 50%;
  display: inline-block;
  margin-right: 0.4rem;
  vertical-align: -2px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 700px) {
  .input-wrap {
    grid-template-columns: 1fr;
  }
}
</style>
