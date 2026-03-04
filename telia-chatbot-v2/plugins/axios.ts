import axios from 'axios'

export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()

  const api = axios.create({
    baseURL: config.public.apiBaseUrl,
    timeout: 30000
  })

  api.interceptors.request.use((requestConfig) => {
    let token = config.public.apiToken

    if (process.client) {
      const localToken = localStorage.getItem('access_token')
      if (localToken) token = localToken
    }

    if (token) {
      requestConfig.headers = requestConfig.headers || {}
      requestConfig.headers.Authorization = `Bearer ${token}`
    }

    return requestConfig
  })

  return {
    provide: {
      api
    }
  }
})
