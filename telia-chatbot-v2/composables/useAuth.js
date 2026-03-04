export const useAuth = () => {
  const token = useState('auth_token', () => '')
  const user = useState('auth_user', () => null)
  const loading = useState('auth_loading', () => false)
  const initialized = useState('auth_initialized', () => false)
  const error = useState('auth_error', () => '')

  const { $api } = useNuxtApp()

  const decodePayload = (jwt) => {
    try {
      const base64 = jwt.split('.')[1]
      if (!base64) return null
      const normalized = base64.replace(/-/g, '+').replace(/_/g, '/')
      const json = decodeURIComponent(
        atob(normalized)
          .split('')
          .map((c) => `%${(`00${c.charCodeAt(0).toString(16)}`).slice(-2)}`)
          .join('')
      )
      return JSON.parse(json)
    } catch {
      return null
    }
  }

  const tokenPayload = computed(() => {
    if (!token.value) return null
    return decodePayload(token.value)
  })

  const tokenExpiresAt = computed(() => {
    const exp = tokenPayload.value?.exp
    if (!exp) return null
    return exp * 1000
  })

  const tokenRemainingSeconds = computed(() => {
    if (!tokenExpiresAt.value) return null
    return Math.max(0, Math.floor((tokenExpiresAt.value - Date.now()) / 1000))
  })

  const isAuthenticated = computed(() => Boolean(token.value && user.value))

  const setStoredToken = (nextToken) => {
    token.value = nextToken || ''

    if (process.client) {
      if (nextToken) localStorage.setItem('access_token', nextToken)
      else localStorage.removeItem('access_token')
    }
  }

  const clearAuth = ({ preserveError = false } = {}) => {
    setStoredToken('')
    user.value = null
    if (!preserveError) {
      error.value = ''
    }
  }

  const fetchMe = async () => {
    const { data } = await $api.get('/auth/me')
    user.value = data
    return data
  }

  const initAuth = async () => {
    if (!process.client || initialized.value) return

    initialized.value = true
    const storedToken = localStorage.getItem('access_token') || ''
    if (!storedToken) return

    setStoredToken(storedToken)

    if (tokenRemainingSeconds.value === 0) {
      clearAuth()
      return
    }

    try {
      loading.value = true
      await fetchMe()
    } catch {
      clearAuth()
    } finally {
      loading.value = false
    }
  }

  const login = async ({ identifier, password }) => {
    const raw = (identifier || '').trim()

    if (!raw || !password) {
      throw new Error('Username/email and password are required.')
    }

    const payload = {
      email: raw,
      username: raw,
      password
    }

    loading.value = true
    error.value = ''

    try {
      const { data } = await $api.post('/auth/login', payload, {
        headers: {
          'Content-Type': 'application/json'
        }
      })

      const accessToken = data?.access_token
      if (!accessToken) throw new Error('No access token returned by login endpoint.')

      setStoredToken(accessToken)
      if (data?.user) {
        user.value = data.user
      }
      try {
        await fetchMe()
      } catch (fetchErr) {
        if (!user.value) {
          throw fetchErr
        }
      }
      return data
    } catch (err) {
      const detail = err?.response?.data?.detail
      if (typeof detail === 'string' && detail.trim()) {
        error.value = detail
      } else if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0]
        error.value = first?.msg || JSON.stringify(first)
      } else if (err?.message) {
        error.value = err.message
      } else {
        error.value = 'Login failed.'
      }
      clearAuth({ preserveError: true })
      throw err
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    clearAuth()
  }

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    tokenExpiresAt,
    tokenRemainingSeconds,
    initAuth,
    login,
    logout,
    clearAuth
  }
}
