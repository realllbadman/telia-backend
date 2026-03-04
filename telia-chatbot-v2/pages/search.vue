<template>
  <main class="page-shell">
    <div class="bg-orb orb-left"></div>
    <div class="bg-orb orb-right"></div>

    <section class="hero">
      <div>
        <p class="eyebrow">Smart Product Discovery</p>
        <h1>Find products by text, image, audio, or video</h1>
        <p class="hero-subtitle">
          Search the catalog faster with natural language, visual matching, voice queries, and short videos.
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

    <section class="searches" :class="{ blocked: !isAuthenticated }">
      <TextSearch
        :language="language"
        :loading="textLoading"
        :disabled="textDisabled"
        @search="handleTextSearch"
      />
      <ImageSearch
        :language="language"
        :loading="imageLoading"
        :disabled="imageDisabled"
        @search="handleImageSearch"
      />
      <AudioSearch
        :language="language"
        :loading="audioLoading"
        :disabled="audioDisabled"
        @search="handleAudioSearch"
      />
      <VideoSearch
        :language="language"
        :loading="videoLoading"
        :disabled="videoDisabled"
        @search="handleVideoSearch"
      />
    </section>

    <p v-if="!isAuthenticated" class="auth-note">
      Sign in above to use text, image, audio, and video recommendations.
    </p>

    <section class="status-area" aria-live="polite">
      <p v-if="loading" class="status loading">Searching recommendations...</p>
      <p v-else-if="error" class="status error">{{ error }}</p>
      <p v-else-if="hasSearched" class="status success">
        {{ recommendations.length }} recommendation{{ recommendations.length === 1 ? '' : 's' }} found.
      </p>
    </section>

    <section v-if="generatedCaption" class="caption-area" aria-live="polite">
      <p class="caption-label">Generated caption</p>
      <p class="caption-text">{{ generatedCaption }}</p>
    </section>

    <ProductGrid :products="recommendations" :loading="loading" :language="language" />
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const language = ref('en')
const textLoading = ref(false)
const imageLoading = ref(false)
const audioLoading = ref(false)
const videoLoading = ref(false)
const loading = computed(() => (
  textLoading.value
  || imageLoading.value
  || audioLoading.value
  || videoLoading.value
))
const error = ref('')
const recommendations = ref([])
const hasSearched = ref(false)
const generatedCaption = ref('')

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
const textDisabled = computed(() => loading.value && !textLoading.value)
const imageDisabled = computed(() => loading.value && !imageLoading.value)
const audioDisabled = computed(() => loading.value && !audioLoading.value)
const videoDisabled = computed(() => loading.value && !videoLoading.value)

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
      imageLoading.value = false
      audioLoading.value = false
      videoLoading.value = false
      generatedCaption.value = ''
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
  hasSearched.value = false
  error.value = ''
  textLoading.value = false
  imageLoading.value = false
  audioLoading.value = false
  videoLoading.value = false
  generatedCaption.value = ''
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
  if (loading.value) return
  if (!ensureAuth()) return

  textLoading.value = true
  error.value = ''
  hasSearched.value = true
  generatedCaption.value = ''

  try {
    const response = await recommendByText({ message, language })
    recommendations.value = response?.recommendations || []
  } catch (err) {
    error.value = getApiErrorMessage(err, 'Failed to fetch text recommendations.')
    recommendations.value = []
  } finally {
    textLoading.value = false
  }
}

const handleImageSearch = async ({ file, language }) => {
  if (loading.value) return
  if (!ensureAuth()) return

  imageLoading.value = true
  error.value = ''
  hasSearched.value = true
  generatedCaption.value = ''

  try {
    const response = await recommendByImage({ file, language })
    recommendations.value = response?.recommendations || []
  } catch (err) {
    error.value = getApiErrorMessage(err, 'Failed to fetch image recommendations.')
    recommendations.value = []
  } finally {
    imageLoading.value = false
  }
}

const handleAudioSearch = async ({ file, language }) => {
  if (loading.value) return
  if (!ensureAuth()) return

  audioLoading.value = true
  error.value = ''
  hasSearched.value = true
  generatedCaption.value = ''

  try {
    const response = await recommendByAudio({ file, language })
    recommendations.value = response?.recommendations || []
  } catch (err) {
    error.value = getApiErrorMessage(err, 'Failed to fetch audio recommendations.')
    recommendations.value = []
  } finally {
    audioLoading.value = false
  }
}

const handleVideoSearch = async ({ file, language }) => {
  if (loading.value) return
  if (!ensureAuth()) return

  videoLoading.value = true
  error.value = ''
  hasSearched.value = true
  generatedCaption.value = ''

  try {
    const response = await recommendByVideo({ file, language })
    generatedCaption.value = response?.caption || ''
    recommendations.value = response?.products || []
  } catch (err) {
    error.value = getApiErrorMessage(err, 'Failed to fetch video recommendations.')
    recommendations.value = []
    generatedCaption.value = ''
  } finally {
    videoLoading.value = false
  }
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

.searches {
  margin-top: 1rem;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
  transition: opacity 0.2s ease;
}

.searches.blocked {
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

@media (max-width: 1400px) {
  .searches {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .hero {
    align-items: start;
    flex-direction: column;
  }

  .language-panel {
    min-width: 100%;
  }

  .searches {
    grid-template-columns: 1fr;
  }
}
</style>
