import { Routes, Route, Navigate, useLocation, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import Login from '@/pages/Login'
import KnowledgeBase from '@/pages/KnowledgeBase'
import UploadCenter from '@/pages/UploadCenter'
import SearchConsole from '@/pages/SearchConsole'
import EvalWorkbench from '@/pages/EvalWorkbench'
import PermissionMgr from '@/pages/PermissionMgr'
import SystemAdmin from '@/pages/SystemAdmin'
import ProductPage from '@/pages/ProductPage'

function RequireAuth() {
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <Outlet />
}

function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<KnowledgeBase />} />
        <Route path="/product" element={<ProductPage />} />
        <Route path="/upload-center" element={<UploadCenter />} />
        <Route path="/search-console" element={<SearchConsole />} />
        <Route path="/eval-workbench" element={<EvalWorkbench />} />
        <Route path="/permission-mgr" element={<PermissionMgr />} />
        <Route path="/system-admin" element={<SystemAdmin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default AppRouter
