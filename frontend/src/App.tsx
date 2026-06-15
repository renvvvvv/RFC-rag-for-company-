import { BrowserRouter } from 'react-router-dom'
import AppLayout from '@/layout/AppLayout'
import AppRouter from '@/router'
import { useAuthStore } from '@/stores/authStore'

function App() {
  const { isAuthenticated } = useAuthStore()

  return (
    <BrowserRouter>
      {isAuthenticated ? (
        <AppLayout>
          <AppRouter />
        </AppLayout>
      ) : (
        <AppRouter />
      )}
    </BrowserRouter>
  )
}

export default App
