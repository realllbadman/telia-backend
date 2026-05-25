export const useApi = () => {
  const { $api } = useNuxtApp()

  const recommendByText = async ({ message, language }) => {
    const payload = { message, language }
    const { data } = await $api.post('/chat/recommend', payload, {
      headers: {
        'Content-Type': 'application/json'
      }
    })
    return data
  }

  const recommendByImage = async ({ file, language, hint = '' }) => {
    const formData = new FormData()
    formData.append('image', file)
    formData.append('language', language)
    if (hint) formData.append('user_hint', hint)

    const { data } = await $api.post('/chat/recommend/image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return data
  }

  const recommendByAudio = async ({ file, language }) => {
    const formData = new FormData()
    const filename = file?.name || 'voice-query.webm'
    formData.append('audio', file, filename)
    formData.append('language', language)

    const { data } = await $api.post('/chat/recommend/audio', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return data
  }

  const recommendByMedia = async ({ file, language }) => {
    const formData = new FormData()
    const filename = file?.name || 'media-query'
    formData.append('media', file, filename)
    formData.append('language', language)

    const { data } = await $api.post('/chat/recommend/media', formData, {
      timeout: 120000,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return data
  }

  const recommendByVideo = async ({ file, language, hint = '' }) => {
    const formData = new FormData()
    const filename = file?.name || 'video-query.mp4'
    formData.append('video', file, filename)
    formData.append('language', language)
    if (hint) formData.append('user_hint', hint)

    const { data } = await $api.post('/chat/recommend/video', formData, {
      timeout: 120000,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return data
  }

  return {
    recommendByText,
    recommendByImage,
    recommendByAudio,
    recommendByMedia,
    recommendByVideo
  }
}
