<template>
  <main class="page-shell">
    <div class="bg-orb orb-left"></div>
    <div class="bg-orb orb-right"></div>

    <section class="hero">
      <div>
        <p class="eyebrow">Smart Product Discovery</p>
        <h1>What can I help you find?</h1>
        <p class="hero-subtitle">
          Use one search bar for text, image, and video. Use microphone search from the same composer.
        </p>
      </div>

      <div class="language-panel">
        <label for="language">Language</label>
        <select id="language" v-model="language" :disabled="loading || authLoading">
          <option value="en">English (EN)</option>
          <option value="fr">Francais (FR)</option>
        </select>
      </div>
    </section>

    <AuthPanel
      :is-authenticated="isAuthenticated"
      :user="authUser"
      :loading="authLoading"
      :error="authError"
      :session-label="sessionLabel"
      @login="handleLogin"
      @logout="handleLogout"
    />

    <section class="composer-shell" :class="{ blocked: !isAuthenticated }">
      <UnifiedSearchBar
        :language="language"
        :loading="loading"
        :disabled="composerDisabled"
        @text-search="handleTextSearch"
        @image-search="handleImageSearch"
        @video-search="handleVideoSearch"
        @document-select="handleDocumentSelect"
        @audio-search="handleAudioSearch"
      />
    </section>

    <p v-if="!isAuthenticated" class="auth-note">
      Sign in above to use text, image, video, and audio recommendations.
    </p>

    <section class="status-area" aria-live="polite">
      <p v-if="loading" class="status loading">Searching recommendations...</p>
      <p v-else-if="error" class="status error">{{ error }}</p>
      <p v-else-if="hasSearched" class="status success">
        {{ recommendations.length }} recommendation{{ recommendations.length === 1 ? '' : 's' }} found.
      </p>
    </section>

    <div v-if="generatedCaption && isGeneratedCaptionVisible" class="caption-toggle">
      <button type="button" class="ghost" @click="showCaption = !showCaption">
        {{ showCaption ? 'Hide generated caption' : 'Show generated caption' }}
      </button>
    </div>

    <section v-if="generatedCaption && isGeneratedCaptionVisible && showCaption" class="caption-area" aria-live="polite">
      <p class="caption-label">Generated search caption</p>
      <p class="caption-text">{{ generatedCaption }}</p>
    </section>

    <ProductGrid
      :products="recommendations"
      :groups="groups"
      :loading="loading"
      :language="language"
      @product-click="handleProductClick"
      @view-all="handleViewAll"
    />
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const language = ref('en')
const textLoading = ref(false)
const mediaLoading = ref(false)
const audioLoading = ref(false)
const loading = computed(() => (
  textLoading.value
  || mediaLoading.value
  || audioLoading.value
))

const error = ref('')
const recommendations = ref([])
const groups = ref([])          // grouped results for multi-intent (image + text)
const hasSearched = ref(false)
const generatedCaption = ref('')
const lastSearchSource = ref('')
const showCaption = ref(false)
let latestTextRequestId = 0

const { recommendByText, recommendByImage, recommendByAudio, recommendByVideo } = useApi()
const {
  user,
  loading: authLoading,
  error: authError,
  isAuthenticated,
  tokenRemainingSeconds,
  initAuth,
  login,
  logout,
  clearAuth
} = useAuth()

const authUser = computed(() => user.value)
const composerDisabled = computed(() => !isAuthenticated.value)
const isGeneratedCaptionVisible = computed(() => ['image', 'audio', 'video'].includes(lastSearchSource.value))

const sessionLabel = computed(() => {
  const seconds = tokenRemainingSeconds.value
  if (seconds === null || !isAuthenticated.value) return ''

  const minutes = Math.floor(seconds / 60)
  const remain = seconds % 60
  return `Session expires in ${minutes}m ${remain}s`
})

onMounted(async () => {
  await initAuth()
})

watch(
  () => tokenRemainingSeconds.value,
  (seconds) => {
    if (seconds === 0 && isAuthenticated.value) {
      logout()
      error.value = 'Session expired. Please sign in again.'
      recommendations.value = []
      textLoading.value = false
      mediaLoading.value = false
      audioLoading.value = false
      generatedCaption.value = ''
      lastSearchSource.value = ''
      showCaption.value = false
    }
  },
  { immediate: true }
)

const handleLogin = async ({ identifier, password }) => {
  error.value = ''
  try {
    await login({ identifier, password })
  } catch {
    // Login error text is exposed through authError
  }
}

const handleLogout = () => {
  logout()
  recommendations.value = []
  groups.value = []
  hasSearched.value = false
  error.value = ''
  textLoading.value = false
  mediaLoading.value = false
  audioLoading.value = false
  generatedCaption.value = ''
  lastSearchSource.value = ''
  showCaption.value = false
}

const getApiErrorMessage = (err, fallbackMessage) => {
  const status = err?.response?.status
  const detail = err?.response?.data?.detail

  if (status === 401 || status === 403) {
    clearAuth()
    return 'Session is not valid anymore. Please sign in again.'
  }

  if (typeof detail === 'string' && detail.trim()) {
    return status ? `${status}: ${detail}` : detail
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    const msg = first?.msg || JSON.stringify(first)
    return status ? `${status}: ${msg}` : msg
  }

  if (err?.message) {
    return err.message
  }

  return fallbackMessage
}

const ensureAuth = () => {
  if (isAuthenticated.value) return true
  error.value = 'Sign in first to use recommendations.'
  return false
}

const handleTextSearch = async ({ message, language }) => {
  if (mediaLoading.value || audioLoading.value) return
  if (!ensureAuth()) return

  const requestId = ++latestTextRequestId
  textLoading.value = true
  error.value = ''
  groups.value = []
  hasSearched.value = true
  generatedCaption.value = ''
  lastSearchSource.value = 'text'
  showCaption.value = false

  try {
    const response = await recommendByText({ message, language })
    if (requestId !== latestTextRequestId) return
    recommendations.value = response?.recommendations || []
    groups.value = response?.groups || []
  } catch (err) {
    if (requestId !== latestTextRequestId) return
    error.value = getApiErrorMessage(err, 'Failed to fetch text recommendations.')
    recommendations.value = []
    groups.value = []
  } finally {
    if (requestId === latestTextRequestId) {
      textLoading.value = false
    }
  }
}

const handleImageSearch = async ({ file, language, hint = '' }) => {
  if (loading.value) return
  if (!ensureAuth()) return

  mediaLoading.value = true
  error.value = ''
  hasSearched.value = true
  generatedCaption.value = ''
  lastSearchSource.value = 'image'
  showCaption.value = false

  try {
    const response = await recommendByImage({ file, language, hint })
    recommendations.value = response?.recommendations || []
    groups.value = response?.groups || []
    generatedCaption.value = (response?.caption || '').trim()
  } catch (err) {
    error.value = getApiErrorMessage(err, 'Failed to fetch image recommendations.')
    recommendations.value = []
    groups.value = []
    generatedCaption.value = ''
  } finally {
    mediaLoading.value = false
  }
}

const handleVideoSearch = async ({ file, language, hint = '' }) => {
  if (loading.value) return
  if (!ensureAuth()) return

  mediaLoading.value = true
  error.value = ''
  hasSearched.value = true
  generatedCaption.value = ''
  lastSearchSource.value = ''
  showCaption.value = false

  try {
    const response = await recommendByVideo({ file, language, hint })
    generatedCaption.value = (response?.caption || '').trim()
    lastSearchSource.value = response?.source || 'video'
    recommendations.value = response?.products || response?.recommendations || []
  } catch (err) {
    error.value = getApiErrorMessage(err, 'Failed to fetch video recommendations.')
    recommendations.value = []
    generatedCaption.value = ''
  } finally {
    mediaLoading.value = false
  }
}

const handleDocumentSelect = ({ file }) => {
  error.value = `Document upload is not available yet: ${file?.name || 'selected file'}`
}

const handleAudioSearch = async ({ file, language }) => {
  if (loading.value) return
  if (!ensureAuth()) return

  audioLoading.value = true
  error.value = ''
  hasSearched.value = true
  generatedCaption.value = ''
  lastSearchSource.value = 'audio'
  showCaption.value = false

  try {
    const response = await recommendByAudio({ file, language })
    recommendations.value = response?.recommendations || []
    generatedCaption.value = (response?.caption || '').trim()
  } catch (err) {
    error.value = getApiErrorMessage(err, 'Failed to fetch audio recommendations.')
    recommendations.value = []
  } finally {
    audioLoading.value = false
  }
}

// Product card click — extend this to open a detail modal/page when ready
const handleProductClick = (product) => {
  // placeholder: log for now, wire to router or modal later
  console.info('[product-click]', product.sku, product.name)
}

// "View all →" click — extend to navigate or filter by category
const handleViewAll = (category) => {
  console.info('[view-all]', category)
}
</script>

<style scoped>
:global(body) {
  background:
    radial-gradient(1200px 600px at -5% 10%, rgba(6, 182, 212, 0.18), transparent 60%),
    radial-gradient(900px 500px at 105% 30%, rgba(34, 197, 94, 0.14), transparent 58%),
    linear-gradient(180deg, #060b14 0%, #0b1220 100%);
}

.page-shell {
  position: relative;
  max-width: 1140px;
  margin: 0 auto;
  padding: 1.2rem;
  min-height: 100vh;
  font-family: 'Segoe UI Variable', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  color: #dbe7f3;
}

.bg-orb {
  position: fixed;
  width: 260px;
  height: 260px;
  border-radius: 50%;
  filter: blur(40px);
  z-index: -1;
  opacity: 0.25;
}

.orb-left {
  top: 4rem;
  left: -4rem;
  background: #0ea5a4;
}

.orb-right {
  top: 12rem;
  right: -5rem;
  background: #16a34a;
}

.hero {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 1rem;
  padding: 1.15rem;
  border-radius: 18px;
  background: linear-gradient(140deg, #0c1628 0%, #101d33 100%);
  border: 1px solid #26364f;
  box-shadow: 0 18px 35px rgba(0, 0, 0, 0.35);
}

.eyebrow {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #5eead4;
  font-weight: 700;
}

h1 {
  margin: 0.35rem 0 0;
  font-size: clamp(1.4rem, 2vw, 2rem);
  color: #e8f0fb;
}

.hero-subtitle {
  margin: 0.45rem 0 0;
  color: #9ab0c8;
  max-width: 50ch;
}

.language-panel {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 200px;
}

.language-panel label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #c4d5e7;
}

.language-panel select {
  border: 1px solid #34475f;
  border-radius: 10px;
  padding: 0.62rem;
  background: #0b1220;
  color: #e5efff;
}

.composer-shell {
  margin-top: 1rem;
  transition: opacity 0.2s ease;
}

.composer-shell.blocked {
  opacity: 0.62;
}

.auth-note {
  margin: 0.7rem 0 0;
  color: #9ab0c8;
  font-size: 0.92rem;
}

.status-area {
  min-height: 2.2rem;
  margin-top: 0.7rem;
}

.status {
  margin: 0;
  border-radius: 10px;
  padding: 0.6rem 0.75rem;
  font-size: 0.92rem;
  border: 1px solid transparent;
}

.status.loading {
  color: #67e8f9;
  background: #082f49;
  border-color: #155e75;
}

.status.error {
  color: #fecaca;
  background: #450a0a;
  border-color: #7f1d1d;
}

.status.success {
  color: #bbf7d0;
  background: #052e16;
  border-color: #166534;
}

.caption-toggle {
  margin-top: 0.4rem;
}

.caption-toggle .ghost {
  border: 1px solid #164e63;
  border-radius: 999px;
  background: #0b1220;
  color: #67e8f9;
  padding: 0.35rem 0.85rem;
  font-size: 0.85rem;
  cursor: pointer;
}

.caption-toggle .ghost:hover {
  border-color: #0ea5a4;
}

.caption-area {
  margin-top: 0.4rem;
  border: 1px solid #164e63;
  border-radius: 12px;
  background: #082f49;
  padding: 0.65rem 0.75rem;
}

.caption-label {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #67e8f9;
}

.caption-text {
  margin: 0.3rem 0 0;
  color: #cffafe;
  line-height: 1.35;
}

@media (max-width: 900px) {
  .hero {
    align-items: start;
    flex-direction: column;
  }

  .language-panel {
    min-width: 100%;
  }
}
</style>
