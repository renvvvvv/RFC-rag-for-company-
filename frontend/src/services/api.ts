import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { message } from 'antd'
import { useAuthStore } from '@/stores/authStore'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败'

    if (status === 401) {
      message.error('登录已过期，请重新登录')
      useAuthStore.getState().logout()
      window.location.href = '/login'
    } else {
      message.error(detail)
    }
    return Promise.reject(error)
  }
)

export default api
