<template>
  <form class="composer" @submit.prevent="submitText">
    <div class="bar" :class="{ disabled: loading || disabled, recording }">
      <AttachmentPicker
        class="icon-button"
        :disabled="loading || disabled"
        :loading="loading"
        @image-selected="onImageSelected"
        @video-selected="onVideoSelected"
        @document-selected="onDocumentSelected"
      >
        +
      </AttachmentPicker>

      <input
        v-model="message"
        type="text"
        class="message-input"
        :disabled="disabled"
        :placeholder="pendingMedia ? 'Add more details (optional)…' : 'Ask anything'"
      />

      <button
        type="button"
        class="icon-button mic"
        :disabled="loading || disabled || !recordingSupported"
        :aria-label="recording ? 'Stop audio recording' : 'Start audio recording'"
        @click="toggleRecording"
      >
        {{ recording ? 'Stop' : 'Mic' }}
      </button>

      <button
        type="submit"
        class="send-button"
        :disabled="loading || disabled || (!message.trim() && !pendingMedia)"
      >
        {{ loading ? '...' : 'Send' }}
      </button>
    </div>

    <div class="meta">
      <span class="language-pill">Language: {{ language.toUpperCase() }}</span>
      <span v-if="recording" class="recording-label">Recording {{ timerLabel }}</span>
      <template v-else-if="pendingMedia">
        <span class="upload-label pending">{{ pendingMediaLabel }} — press Send to search</span>
        <button type="button" class="clear-btn" aria-label="Remove attachment" @click="clearPendingMedia">✕</button>
      </template>
      <span v-else-if="lastUploadedLabel" class="upload-label">{{ lastUploadedLabel }}</span>
      <span v-else class="hint">Use + for photos, camera, video, and documents. Use Mic for audio.</span>
    </div>

    <p v-if="recordingError" class="error">{{ recordingError }}</p>
  </form>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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

const emit = defineEmits(['text-search', 'image-search', 'video-search', 'document-select', 'audio-search'])

const message = ref('')
const lastUploadedLabel = ref('')

// Pending media: holds file + type until user clicks Send
const pendingMedia = ref(null) // { file: File, type: 'image' | 'video' }
const pendingMediaLabel = ref('')

const recordingSupported = ref(false)
const recording = ref(false)
const recordingError = ref('')
const seconds = ref(0)

const mediaRecorder = ref(null)
const mediaStream = ref(null)

let timerId = null
let autoSearchTimer = null

const timerLabel = computed(() => {
  const mins = Math.floor(seconds.value / 60)
  const secs = String(seconds.value % 60).padStart(2, '0')
  return `${mins}:${secs}`
})

const formatFileSize = (size) => {
  const kb = size / 1024
  if (kb < 1024) return `${Math.round(kb)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
}

const updateUploadedLabel = (selected, prefix) => {
  recordingError.value = ''
  lastUploadedLabel.value = `${prefix}: ${selected.name} (${formatFileSize(selected.size)})`
}

const onImageSelected = (selected) => {
  if (!selected) return
  recordingError.value = ''
  lastUploadedLabel.value = ''
  pendingMedia.value = { file: selected, type: 'image' }
  pendingMediaLabel.value = `Photo: ${selected.name} (${formatFileSize(selected.size)})`
}

const onVideoSelected = (selected) => {
  if (!selected) return
  recordingError.value = ''
  lastUploadedLabel.value = ''
  pendingMedia.value = { file: selected, type: 'video' }
  pendingMediaLabel.value = `Video: ${selected.name} (${formatFileSize(selected.size)})`
}

const clearPendingMedia = () => {
  pendingMedia.value = null
  pendingMediaLabel.value = ''
}

const onDocumentSelected = (selected) => {
  if (!selected) return
  updateUploadedLabel(selected, 'Document')
  emit('document-select', {
    file: selected,
    language: props.language
  })
}

const clearAutoSearchTimer = () => {
  if (!autoSearchTimer) return
  clearTimeout(autoSearchTimer)
  autoSearchTimer = null
}

const emitTextSearch = ({ clearAfter = false, ignoreLoading = false } = {}) => {
  if (props.disabled) return
  if (!ignoreLoading && props.loading) return
  const text = message.value.trim()
  if (!text) return

  emit('text-search', {
    message: text,
    language: props.language
  })
  if (clearAfter) {
    message.value = ''
  }
}

const submitText = () => {
  clearAutoSearchTimer()

  if (pendingMedia.value) {
    if (props.disabled || props.loading) return
    const { file, type } = pendingMedia.value
    const hint = message.value.trim()
    const label = pendingMediaLabel.value
    pendingMedia.value = null
    pendingMediaLabel.value = ''
    lastUploadedLabel.value = label

    if (type === 'image') {
      emit('image-search', { file, language: props.language, hint })
    } else {
      emit('video-search', { file, language: props.language, hint })
    }
    return
  }

  emitTextSearch()
}

watch(
  () => [message.value, props.language, props.disabled],
  () => {
    clearAutoSearchTimer()
    if (props.disabled) return
    // Don't auto-search while a media file is pending — user may be typing a hint
    if (pendingMedia.value) return

    const text = message.value.trim()
    if (text.length < 2) return

    autoSearchTimer = setTimeout(() => {
      emitTextSearch({ ignoreLoading: true })
    }, 350)
  }
)

const stopMediaStream = () => {
  if (!mediaStream.value) return
  mediaStream.value.getTracks().forEach((track) => track.stop())
  mediaStream.value = null
}

const clearTimer = () => {
  if (!timerId) return
  clearInterval(timerId)
  timerId = null
}

const detectMimeType = () => {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4'
  ]

  if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') {
    return ''
  }

  return candidates.find((mime) => MediaRecorder.isTypeSupported(mime)) || ''
}

const startRecording = async () => {
  if (props.loading || props.disabled || !recordingSupported.value) return

  recordingError.value = ''
  lastUploadedLabel.value = ''

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1
      }
    })

    mediaStream.value = stream
    const mimeType = detectMimeType()
    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream)

    const chunks = []
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data)
      }
    }

    recorder.onstop = () => {
      const audioType = recorder.mimeType || mimeType || 'audio/webm'
      const audioBlob = new Blob(chunks, { type: audioType })
      if (!audioBlob.size) {
        recordingError.value = 'No audio captured. Please try recording again.'
        stopMediaStream()
        return
      }

      const extension = audioType.includes('ogg')
        ? 'ogg'
        : audioType.includes('mp4')
          ? 'm4a'
          : 'webm'

      const audioFile = new File(
        [audioBlob],
        `voice-query-${Date.now()}.${extension}`,
        { type: audioBlob.type || 'audio/webm' }
      )

      lastUploadedLabel.value = `Recorded: ${audioFile.name} (${formatFileSize(audioFile.size)})`
      emit('audio-search', {
        file: audioFile,
        language: props.language
      })
      stopMediaStream()
    }

    mediaRecorder.value = recorder
    recording.value = true
    seconds.value = 0
    timerId = setInterval(() => {
      seconds.value += 1
    }, 1000)

    recorder.start(250)
  } catch (err) {
    recordingError.value = err?.message || 'Microphone access failed.'
    recording.value = false
    clearTimer()
    stopMediaStream()
  }
}

const stopRecording = () => {
  if (!recording.value || !mediaRecorder.value) return
  recording.value = false
  clearTimer()
  mediaRecorder.value.stop()
  mediaRecorder.value = null
}

const toggleRecording = () => {
  if (recording.value) {
    stopRecording()
    return
  }
  startRecording()
}

onMounted(() => {
  recordingSupported.value = (
    typeof window !== 'undefined'
    && typeof navigator !== 'undefined'
    && Boolean(navigator.mediaDevices?.getUserMedia)
    && typeof MediaRecorder !== 'undefined'
  )
})

onBeforeUnmount(() => {
  clearAutoSearchTimer()
  clearTimer()
  if (mediaRecorder.value && recording.value) {
    mediaRecorder.value.stop()
  }
  stopMediaStream()
})
</script>

<style scoped>
.composer {
  width: min(980px, 100%);
  margin: 0 auto;
}

.attachment-picker {
  display: flex;
}

.hidden-input {
  display: none;
}

.bar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem;
  border-radius: 999px;
  border: 1px solid #334155;
  background: linear-gradient(180deg, #1e293b 0%, #111827 100%);
  box-shadow: 0 18px 32px rgba(0, 0, 0, 0.38);
}

.bar.recording {
  border-color: #dc2626;
  box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.25);
}

.bar.disabled {
  opacity: 0.72;
}

.icon-button,
.send-button {
  height: 42px;
  border: none;
  border-radius: 999px;
  padding: 0 0.95rem;
  font-size: 0.95rem;
  cursor: pointer;
  color: #e2e8f0;
  background: #111827;
  border: 1px solid #334155;
}

.icon-button:hover:not(:disabled),
.send-button:hover:not(:disabled) {
  border-color: #64748b;
}

.icon-button:disabled,
.send-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.icon-button {
  min-width: 42px;
}

.icon-button.mic {
  min-width: 54px;
}

.send-button {
  background: linear-gradient(135deg, #0f766e 0%, #0891b2 100%);
  border-color: #0f766e;
  color: #ffffff;
}

.message-input {
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: #e5e7eb;
  font-size: 1.02rem;
  padding: 0.25rem 0;
}

.message-input::placeholder {
  color: #94a3b8;
}

.meta {
  margin-top: 0.55rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
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

.recording-label,
.upload-label,
.hint {
  color: #cbd5e1;
  font-size: 0.9rem;
}

.recording-label {
  color: #fca5a5;
}

.upload-label.pending {
  color: #5eead4;
}

.clear-btn {
  background: none;
  border: 1px solid #334155;
  border-radius: 999px;
  color: #94a3b8;
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1;
  padding: 0.15rem 0.45rem;
}

.clear-btn:hover {
  border-color: #64748b;
  color: #fca5a5;
}

.error {
  margin: 0.5rem 0 0;
  color: #fca5a5;
  font-size: 0.88rem;
}

@media (max-width: 760px) {
  .bar {
    grid-template-columns: auto minmax(0, 1fr) auto;
    grid-template-areas:
      "attach input send"
      "mic mic mic";
    border-radius: 18px;
    gap: 0.45rem;
    padding: 0.55rem;
  }

  .attachment-picker {
    grid-area: attach;
  }

  .message-input {
    grid-area: input;
  }

  .send-button {
    grid-area: send;
  }

  .icon-button.mic {
    grid-area: mic;
    width: 100%;
    min-width: 0;
  }
}
</style>
