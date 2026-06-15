import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

export interface User {
  id: string
  username: string
  email: string
  department?: string
  security_level: string
  role_id?: string | null
  status: string
}

interface AuthState {
  token: string | null
  isAuthenticated: boolean
  user: User | null
  setToken: (token: string) => void
  setUser: (user: User) => void
  logout: () => void
}

const storedToken = localStorage.getItem('token')

export const useAuthStore = create<AuthState>()(
  immer((set) => ({
    token: storedToken,
    isAuthenticated: !!storedToken,
    user: null,
    setToken: (token) =>
      set((state) => {
        state.token = token
        state.isAuthenticated = true
        localStorage.setItem('token', token)
      }),
    setUser: (user) =>
      set((state) => {
        state.user = user
      }),
    logout: () =>
      set((state) => {
        state.token = null
        state.isAuthenticated = false
        state.user = null
        localStorage.removeItem('token')
      }),
  }))
)
