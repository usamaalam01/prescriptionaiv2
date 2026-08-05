import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

export const api = axios.create({
  baseURL: '',
})

function setHeader(config: InternalAxiosRequestConfig, key: string, value: string) {
  const headers = config.headers
  if (headers && typeof (headers as { set?: (k: string, v: string) => void }).set === 'function') {
    ;(headers as { set: (k: string, v: string) => void }).set(key, value)
  } else {
    config.headers = config.headers ?? {}
    ;(config.headers as Record<string, string>)[key] = value
  }
}

function deleteHeader(config: InternalAxiosRequestConfig, key: string) {
  const headers = config.headers as { delete?: (k: string) => void; [k: string]: unknown } | undefined
  if (!headers) return
  if (typeof headers.delete === 'function') {
    headers.delete(key)
  } else {
    delete headers[key]
  }
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    setHeader(config, 'Authorization', `Bearer ${token}`)
  }

  // Browser must set multipart boundary for FormData.
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    deleteHeader(config, 'Content-Type')
  } else if (config.data !== undefined && config.method?.toLowerCase() !== 'get') {
    setHeader(config, 'Content-Type', 'application/json')
  }

  return config
})

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = localStorage.getItem('refresh_token')
  if (!refresh) return null
  try {
    const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refresh })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    if (data.user) {
      localStorage.setItem('user', JSON.stringify(data.user))
    }
    return data.access_token as string
  } catch {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    return null
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
    if (!original || error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }
    // Don't try to refresh the refresh/login endpoints themselves
    if (original.url?.includes('/auth/login') || original.url?.includes('/auth/refresh')) {
      return Promise.reject(error)
    }

    original._retry = true
    refreshPromise = refreshPromise ?? refreshAccessToken().finally(() => {
      refreshPromise = null
    })
    const newToken = await refreshPromise
    if (!newToken) {
      return Promise.reject(error)
    }
    setHeader(original, 'Authorization', `Bearer ${newToken}`)
    return api(original)
  },
)
