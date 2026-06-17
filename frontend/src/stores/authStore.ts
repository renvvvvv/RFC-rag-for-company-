import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

export interface User {
  id: string
  username: string
  email: string
  department?: string
  security_level: string
  role?: string
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

// Security note: httpOnly cookies are the ideal storage for JWTs because they
// are inaccessible to JavaScript and mitigate XSS token exfiltration.
// sessionStorage is used for runtime tokens so they are cleared when the tab
// closes. The optional __playwright_token__ localStorage key is only used by
// E2E tests because Playwright's storageState cannot capture sessionStorage.
const storedToken =
  sessionStorage.getItem('token') || localStorage.getItem('__playwright_token__') || null

export const useAuthStore = create<AuthState>()(
  immer((set) => ({
    token: storedToken,
    isAuthenticated: !!storedToken,
    user: null,
    setToken: (token) =>
      set((state) => {
        state.token = token
        state.isAuthenticated = true
        sessionStorage.setItem('token', token)
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
        sessionStorage.removeItem('token')
        localStorage.removeItem('__playwright_token__')
      }),
  }))
)
