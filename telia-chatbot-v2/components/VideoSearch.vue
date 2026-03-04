<template>
  <form class="search-card" @submit.prevent="onSubmit">
    <div class="card-header">
      <p class="eyebrow">Search by video</p>
      <h2>Upload a short product video</h2>
      <p class="subtitle">We sample frames, generate a caption, and fetch matching catalog products.</p>
    </div>

    <div class="upload-area" :class="{ 'has-file': !!file }">
      <input
        id="videoInput"
        ref="fileInput"
        type="file"
        accept="video/*,.mp4,.mov,.avi,.mkv,.webm,.m4v,.mpeg,.mpg"
        :disabled="loading || disabled"
        @change="onFileChange"
      />

      <label for="videoInput" class="upload-button">
        {{ file ? 'Change video' : 'Choose video' }}
      </label>

      <p class="upload-text" v-if="file">
        {{ file.name }} ({{ fileSizeLabel }})
      </p>
      <p class="upload-text" v-else>
        No file selected
      </p>
    </div>

    <div class="actions">
      <span class="language-pill">Language: {{ language.toUpperCase() }}</span>
      <div class="buttons">
        <button type="button" class="ghost" :disabled="loading || disabled || !file" @click="clearFile">Clear</button>
        <button type="submit" :disabled="loading || disabled || !file">
          <span v-if="loading" class="spinner" aria-hidden="true"></span>
          {{ loading ? 'Searching' : 'Search video' }}
        </button>
      </div>
    </div>
  </form>
</template>

<script setup>
import { computed, ref } from 'vue'

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
const file = ref(null)
const fileInput = ref(null)

const fileSizeLabel = computed(() => {
  if (!file.value?.size) return '0 KB'
  const kb = file.value.size / 1024
  if (kb < 1024) return `${Math.round(kb)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
})

const onFileChange = (event) => {
  const selected = event.target.files?.[0]
  file.value = selected || null
}

const clearFile = () => {
  file.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const onSubmit = () => {
  if (!file.value) return

  emit('search', {
    file: file.value,
    language: props.language
  })
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

.upload-area {
  border: 1px dashed #3b4f67;
  border-radius: 12px;
  padding: 0.8rem;
  background: #0b1220;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.upload-area.has-file {
  border-color: #14b8a6;
  background: #0f1d2f;
}

input[type='file'] {
  display: none;
}

.upload-button {
  display: inline-block;
  border: 1px solid #14b8a6;
  border-radius: 10px;
  background: #111f33;
  color: #c2ebff;
  padding: 0.45rem 0.8rem;
  font-weight: 600;
  cursor: pointer;
}

.upload-text {
  margin: 0.6rem 0 0;
  color: #99afc7;
  font-size: 0.9rem;
  word-break: break-word;
}

.actions {
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

.buttons {
  display: flex;
  gap: 0.45rem;
}

button {
  border: none;
  border-radius: 10px;
  padding: 0.62rem 0.95rem;
  background: linear-gradient(135deg, #0f766e 0%, #0891b2 100%);
  color: #fff;
  cursor: pointer;
  font-weight: 600;
}

button.ghost {
  background: #1e293b;
  color: #c7d2fe;
}

button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
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
</style>
