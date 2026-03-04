<template>
  <form class="search-card" @submit.prevent="onSubmit">
    <div class="card-header">
      <p class="eyebrow">Search by audio</p>
      <h2>Record a voice query</h2>
      <p class="subtitle">Use your microphone, then we transcribe and match products.</p>
    </div>

    <div class="record-area" :class="{ active: recording, ready: !!recordedFile }">
      <p v-if="!recording && !recordedFile" class="record-text">No recording yet</p>
      <p v-else-if="recording" class="record-text recording">
        <span class="dot" aria-hidden="true"></span>
        Recording {{ timerLabel }}
      </p>
      <p v-else class="record-text">
        Recording ready: {{ recordedLabel }}
      </p>

      <audio v-if="audioPreviewUrl" class="player" :src="audioPreviewUrl" controls />
      <p v-if="recordingError" class="error">{{ recordingError }}</p>
    </div>

    <div class="actions">
      <span class="language-pill">Language: {{ language.toUpperCase() }}</span>

      <div class="buttons">
        <button
          v-if="!recording"
          type="button"
          class="record-btn"
          :disabled="loading || disabled || !recordingSupported"
          @click="startRecording"
        >
          Start recording
        </button>

        <button
          v-else
          type="button"
          class="stop-btn"
          :disabled="loading || disabled"
          @click="stopRecording"
        >
          Stop
        </button>

        <button
          type="button"
          class="ghost"
          :disabled="loading || disabled || recording || !recordedFile"
          @click="clearRecording"
        >
          Clear
        </button>

        <button type="submit" :disabled="loading || disabled || recording || !recordedFile">
          <span v-if="loading" class="spinner" aria-hidden="true"></span>
          {{ loading ? 'Searching' : 'Search audio' }}
        </button>
      </div>
    </div>

    <p v-if="!recordingSupported" class="hint">
      Microphone recording is not supported in this browser.
    </p>
  </form>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

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

const recordingSupported = ref(false)
const recording = ref(false)
const recordedFile = ref(null)
const audioPreviewUrl = ref('')
const recordingError = ref('')
const seconds = ref(0)

const mediaRecorder = ref(null)
const mediaStream = ref(null)

let timerId = null

const timerLabel = computed(() => {
  const mins = Math.floor(seconds.value / 60)
  const secs = String(seconds.value % 60).padStart(2, '0')
  return `${mins}:${secs}`
})

const recordedLabel = computed(() => {
  if (!recordedFile.value) return ''
  const kb = recordedFile.value.size / 1024
  if (kb < 1024) return `${Math.round(kb)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
})

const stopMediaStream = () => {
  if (!mediaStream.value) return
  mediaStream.value.getTracks().forEach((track) => track.stop())
  mediaStream.value = null
}

const clearTimer = () => {
  if (timerId) {
    clearInterval(timerId)
    timerId = null
  }
}

const revokePreviewUrl = () => {
  if (audioPreviewUrl.value) {
    URL.revokeObjectURL(audioPreviewUrl.value)
    audioPreviewUrl.value = ''
  }
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

  const supported = candidates.find((mime) => MediaRecorder.isTypeSupported(mime))
  return supported || ''
}

const clearRecording = () => {
  recordedFile.value = null
  revokePreviewUrl()
  recordingError.value = ''
  seconds.value = 0
}

const startRecording = async () => {
  if (props.loading || props.disabled) return

  clearRecording()
  recordingError.value = ''

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
      const extension = audioType.includes('ogg')
        ? 'ogg'
        : audioType.includes('mp4')
          ? 'm4a'
          : 'webm'

      recordedFile.value = new File(
        [audioBlob],
        `voice-query-${Date.now()}.${extension}`,
        { type: audioBlob.type || 'audio/webm' }
      )

      revokePreviewUrl()
      audioPreviewUrl.value = URL.createObjectURL(recordedFile.value)
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

const onSubmit = () => {
  if (!recordedFile.value || recording.value) return
  emit('search', {
    file: recordedFile.value,
    language: props.language
  })
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
  clearTimer()
  if (mediaRecorder.value && recording.value) {
    mediaRecorder.value.stop()
  }
  stopMediaStream()
  revokePreviewUrl()
})
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

.record-area {
  border: 1px dashed #3b4f67;
  border-radius: 12px;
  padding: 0.9rem;
  background: #0b1220;
}

.record-area.active {
  border-color: #f43f5e;
  background: #29121c;
}

.record-area.ready {
  border-color: #14b8a6;
  background: #0f1d2f;
}

.record-text {
  margin: 0;
  color: #c4d5e7;
  font-size: 0.92rem;
}

.record-text.recording {
  color: #fecdd3;
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #fb7185;
  box-shadow: 0 0 0 6px rgba(251, 113, 133, 0.15);
}

.player {
  width: 100%;
  margin-top: 0.7rem;
}

.error {
  margin: 0.65rem 0 0;
  color: #fca5a5;
  font-size: 0.88rem;
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
  flex-wrap: wrap;
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

.record-btn {
  background: linear-gradient(135deg, #c2410c 0%, #ea580c 100%);
}

.stop-btn {
  background: linear-gradient(135deg, #be123c 0%, #ef4444 100%);
}

button.ghost {
  background: #1e293b;
  color: #c7d2fe;
}

button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.hint {
  margin: 0.7rem 0 0;
  color: #fca5a5;
  font-size: 0.85rem;
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
