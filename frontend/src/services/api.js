import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30_000,
  headers: { Accept: 'application/json' },
})

api.interceptors.response.use(
  response => response,
  error => {
    if (error.code === 'ECONNABORTED') {
      error.userMessage = 'Backend nije odgovorio unutar 30 sekundi.'
    } else if (!error.response) {
      error.userMessage = 'Backend nije dostupan. Provjeri je li FastAPI pokrenut.'
    }
    return Promise.reject(error)
  },
)

export function errorMessage(error, fallback = 'Zahtjev nije uspio.') {
  return error?.response?.data?.detail ?? error?.userMessage ?? fallback
}

export default api
