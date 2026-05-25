<template>
  <div class="attachment-picker">
    <input
      ref="photoInput"
      class="hidden-input"
      type="file"
      accept="image/*"
      :disabled="disabled || loading"
      @change="onPhotoSelected"
    />

    <input
      ref="videoInput"
      class="hidden-input"
      type="file"
      accept="video/*,.mp4,.mov,.avi,.mkv,.webm,.m4v,.mpeg,.mpg"
      :disabled="disabled || loading"
      @change="onVideoSelected"
    />

    <input
      ref="documentInput"
      class="hidden-input"
      type="file"
      accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      :disabled="disabled || loading"
      @change="onDocumentSelected"
    />

    <button
      type="button"
      class="trigger"
      v-bind="triggerAttrs"
      :disabled="disabled || loading"
      aria-label="Open attachment picker"
      @click="openSheet"
    >
      <slot>+</slot>
    </button>

    <Teleport to="body">
      <Transition name="sheet-fade">
        <div v-if="sheetOpen" class="sheet-overlay" @click.self="closeSheet">
          <div class="sheet" role="dialog" aria-modal="true" aria-label="Attachment picker">
            <div class="sheet-handle"></div>

            <div class="sheet-head">
              <div>
                <p class="eyebrow">Attachments</p>
                <h3>Share something</h3>
              </div>
              <button type="button" class="close-button" aria-label="Close attachment picker" @click="closeSheet">
                x
              </button>
            </div>

            <div class="grid">
              <button type="button" class="tile photos" :disabled="disabled || loading" @click="pickPhotos">
                <span class="icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path d="M4 7.5A2.5 2.5 0 0 1 6.5 5h11A2.5 2.5 0 0 1 20 7.5v9A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5v-9Z" />
                    <path d="M8 15l2.6-2.8a1 1 0 0 1 1.47-.02L14 14l1.1-1.05a1 1 0 0 1 1.39.01L20 16.5" />
                    <circle cx="9" cy="9" r="1.4" />
                  </svg>
                </span>
                <span class="label">Photos</span>
              </button>

              <button type="button" class="tile camera" :disabled="disabled || loading" @click="openCamera">
                <span class="icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path d="M7.5 7 9 5h6l1.5 2H19a2 2 0 0 1 2 2v7.5A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5V9a2 2 0 0 1 2-2h2.5Z" />
                    <circle cx="12" cy="13" r="3.25" />
                  </svg>
                </span>
                <span class="label">Camera</span>
              </button>

              <button type="button" class="tile video" :disabled="disabled || loading" @click="pickVideo">
                <span class="icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none">
                    <rect x="3.5" y="5.5" width="11" height="13" rx="2.5" />
                    <path d="m14.5 10.2 4.6-2.8a.6.6 0 0 1 .9.52v8.2a.6.6 0 0 1-.9.51l-4.6-2.8" />
                  </svg>
                </span>
                <span class="label">Video</span>
              </button>

              <button type="button" class="tile document" :disabled="disabled || loading" @click="pickDocument">
                <span class="icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path d="M7 3.5h6.8L19 8.7v10.8A1.5 1.5 0 0 1 17.5 21h-10A1.5 1.5 0 0 1 6 19.5v-14A2 2 0 0 1 8 3.5Z" />
                    <path d="M13.5 3.5v4.2A1.3 1.3 0 0 0 14.8 9H19" />
                    <path d="M8.8 13h6.4M8.8 16.2h4.4" />
                  </svg>
                </span>
                <span class="label">Document</span>
              </button>

            </div>

            <p v-if="cameraError" class="camera-error">{{ cameraError }}</p>
          </div>
        </div>
      </Transition>

      <Transition name="sheet-fade">
        <div v-if="cameraOpen" class="sheet-overlay camera-overlay" @click.self="closeCamera">
          <div class="camera-sheet" role="dialog" aria-modal="true" aria-label="Camera capture">
            <div class="sheet-head">
              <div>
                <p class="eyebrow">Camera</p>
                <h3>Take a photo</h3>
              </div>
              <button type="button" class="close-button" aria-label="Close camera" @click="closeCamera">
                x
              </button>
            </div>

            <div class="camera-stage" :class="{ unavailable: !cameraReady }">
              <video v-show="cameraReady" ref="videoPreview" autoplay playsinline muted></video>
              <div v-if="!cameraReady" class="camera-empty">
                {{ cameraError || 'Starting camera...' }}
              </div>
            </div>

            <div class="camera-actions">
              <button type="button" class="ghost-button" @click="closeCamera">Cancel</button>
              <button type="button" class="capture-button" :disabled="!cameraReady" @click="capturePhoto">
                Capture
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false
})

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['image-selected', 'video-selected', 'document-selected'])
const triggerAttrs = useAttrs()

const sheetOpen = ref(false)
const cameraOpen = ref(false)
const cameraReady = ref(false)
const cameraError = ref('')

const photoInput = ref(null)
const videoInput = ref(null)
const documentInput = ref(null)
const videoPreview = ref(null)
const mediaStream = ref(null)

const openSheet = () => {
  if (props.disabled || props.loading) return
  cameraError.value = ''
  sheetOpen.value = true
}

const closeSheet = () => {
  sheetOpen.value = false
}

const triggerInput = (inputRef) => {
  inputRef.value?.click()
}

const resetInput = (inputRef) => {
  if (inputRef.value) {
    inputRef.value.value = ''
  }
}

const emitFile = (event, inputRef, emitName) => {
  const selected = event.target.files?.[0]
  if (!selected) return
  closeSheet()
  emit(emitName, selected)
  resetInput(inputRef)
}

const pickPhotos = () => {
  triggerInput(photoInput)
}

const pickVideo = () => {
  triggerInput(videoInput)
}

const pickDocument = () => {
  triggerInput(documentInput)
}

const onPhotoSelected = (event) => {
  emitFile(event, photoInput, 'image-selected')
}

const onVideoSelected = (event) => {
  emitFile(event, videoInput, 'video-selected')
}

const onDocumentSelected = (event) => {
  emitFile(event, documentInput, 'document-selected')
}

const stopCameraStream = () => {
  if (!mediaStream.value) return
  mediaStream.value.getTracks().forEach((track) => track.stop())
  mediaStream.value = null
}

const closeCamera = () => {
  cameraOpen.value = false
  cameraReady.value = false
  stopCameraStream()
}

const openCamera = async () => {
  if (props.disabled || props.loading) return

  cameraError.value = ''
  closeSheet()
  cameraOpen.value = true
  cameraReady.value = false

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'environment'
      },
      audio: false
    })

    mediaStream.value = stream
    await nextTick()

    if (videoPreview.value) {
      videoPreview.value.srcObject = stream
      await videoPreview.value.play()
    }

    cameraReady.value = true
  } catch (err) {
    cameraError.value = err?.message || 'Camera access failed.'
    cameraReady.value = false
  }
}

const capturePhoto = () => {
  const video = videoPreview.value
  if (!video || !cameraReady.value) return

  const width = video.videoWidth || 1280
  const height = video.videoHeight || 720
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height

  const context = canvas.getContext('2d')
  if (!context) {
    cameraError.value = 'Camera capture is not available in this browser.'
    return
  }

  context.drawImage(video, 0, 0, width, height)
  canvas.toBlob((blob) => {
    if (!blob) {
      cameraError.value = 'Failed to capture image.'
      return
    }

    const file = new File(
      [blob],
      `camera-capture-${Date.now()}.jpg`,
      { type: 'image/jpeg' }
    )

    closeCamera()
    emit('image-selected', file)
  }, 'image/jpeg', 0.92)
}

onBeforeUnmount(() => {
  stopCameraStream()
})
</script>

<style scoped>
.hidden-input {
  display: none;
}

.trigger {
  min-width: 42px;
}

.sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.7);
  backdrop-filter: blur(10px);
  display: grid;
  align-items: end;
  z-index: 40;
  padding: 1rem;
}

.sheet,
.camera-sheet {
  width: min(560px, 100%);
  margin: 0 auto;
  border: 1px solid rgba(71, 85, 105, 0.7);
  border-radius: 24px;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 164, 0.18), transparent 35%),
    linear-gradient(180deg, #09111f 0%, #0f172a 100%);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);
  color: #e2e8f0;
}

.sheet {
  padding: 0.75rem 0.85rem 1rem;
}

.camera-sheet {
  align-self: center;
  padding: 0.9rem;
}

.sheet-handle {
  width: 54px;
  height: 5px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.4);
  margin: 0 auto 0.9rem;
}

.sheet-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: start;
  margin-bottom: 0.95rem;
}

.eyebrow {
  margin: 0;
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #67e8f9;
  font-weight: 700;
}

h3 {
  margin: 0.3rem 0 0;
  font-size: 1.15rem;
  color: #f8fafc;
}

.close-button,
.ghost-button,
.capture-button {
  border: 1px solid #334155;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.92);
  color: #e2e8f0;
  cursor: pointer;
}

.close-button {
  width: 38px;
  height: 38px;
  font-size: 0.95rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
}

.tile {
  border: 1px solid rgba(71, 85, 105, 0.8);
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.92);
  min-height: 108px;
  padding: 0.9rem 0.75rem;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.65rem;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.tile:hover:not(:disabled) {
  transform: translateY(-2px);
}

.tile:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.tile.photos:hover:not(:disabled) {
  border-color: #38bdf8;
  background: rgba(8, 47, 73, 0.96);
}

.tile.camera:hover:not(:disabled) {
  border-color: #2dd4bf;
  background: rgba(15, 58, 55, 0.96);
}

.tile.video:hover:not(:disabled) {
  border-color: #818cf8;
  background: rgba(30, 27, 75, 0.96);
}

.tile.document:hover:not(:disabled) {
  border-color: #f59e0b;
  background: rgba(69, 26, 3, 0.96);
}

.icon {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: rgba(30, 41, 59, 0.9);
}

.icon svg {
  width: 26px;
  height: 26px;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.photos .icon {
  color: #7dd3fc;
}

.camera .icon {
  color: #5eead4;
}

.video .icon {
  color: #a5b4fc;
}

.document .icon {
  color: #fbbf24;
}

.label {
  font-weight: 600;
  color: #e2e8f0;
}

.camera-stage {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  border: 1px solid #334155;
  min-height: 280px;
  background: #020617;
  display: grid;
  place-items: center;
}

.camera-stage video {
  width: 100%;
  max-height: 65vh;
  display: block;
  object-fit: cover;
}

.camera-stage.unavailable {
  background:
    radial-gradient(circle at top, rgba(239, 68, 68, 0.12), transparent 30%),
    #020617;
}

.camera-empty {
  padding: 1rem;
  color: #cbd5e1;
  text-align: center;
}

.camera-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  margin-top: 0.95rem;
}

.ghost-button,
.capture-button {
  padding: 0.72rem 1rem;
  font-weight: 600;
}

.capture-button {
  border-color: #0f766e;
  background: linear-gradient(135deg, #0f766e 0%, #0891b2 100%);
  color: #ffffff;
}

.capture-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.camera-error {
  margin: 0.85rem 0 0;
  color: #fca5a5;
  font-size: 0.9rem;
}

.sheet-fade-enter-active,
.sheet-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.sheet-fade-enter-from,
.sheet-fade-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .sheet-overlay {
    padding: 0.6rem;
  }

  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .tile {
    min-height: 96px;
  }
}
</style>
