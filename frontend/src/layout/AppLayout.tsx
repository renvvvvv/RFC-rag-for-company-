import type React from 'react'
import { useEffect, useMemo, useState } from 'react'
import { Layout, Menu, Avatar, Space, Typography, Button, Badge } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  DatabaseOutlined,
  UploadOutlined,
  SearchOutlined,
  LineChartOutlined,
  SafetyOutlined,
  SettingOutlined,
  ProfileOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/authStore'
import { colors, spacing, radius, shadows, typography } from '@/styles/theme'
import api from '@/services/api'

const { Header, Sider, Content } = Layout

interface AppLayoutProps {
  children: React.ReactNode
}

const ALL_MENU_ITEMS = [
  { key: '/', icon: <DatabaseOutlined />, label: '知识库' },
  { key: '/product', icon: <ProfileOutlined />, label: '产品方案' },
  { key: '/upload-center', icon: <UploadOutlined />, label: '上传中心' },
  { key: '/search-console', icon: <SearchOutlined />, label: '检索控制台' },
  { key: '/eval-workbench', icon: <LineChartOutlined />, label: '评测工作台' },
  { key: '/permission-mgr', icon: <SafetyOutlined />, label: '权限管理', adminOnly: true },
  { key: '/system-admin', icon: <SettingOutlined />, label: '系统管理', adminOnly: true },
]

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  const isAdmin = user ? user.role === 'admin' || user.security_level === 'L4' : false

  const menuItems = useMemo(
    () => ALL_MENU_ITEMS.filter((item) => !item.adminOnly || isAdmin),
    [isAdmin]
  )

  const [systemStatus, setSystemStatus] = useState<'success' | 'warning' | 'error'>('success')

  useEffect(() => {
    let mounted = true
    const checkHealth = async () => {
      if (document.hidden) return
      try {
        const res = await api.get('/v1/health')
        if (!mounted) return
        setSystemStatus(res.data.status === 'ok' ? 'success' : 'warning')
      } catch {
        if (!mounted) return
        setSystemStatus('error')
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    const handleVisibility = () => {
      if (!document.hidden) checkHealth()
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => {
      mounted = false
      clearInterval(interval)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [])

  return (
    <Layout style={{ minHeight: '100vh', overflowX: 'hidden', background: colors.background }}>
      <Sider
        theme="light"
        width={230}
        style={{
          background: colors.surface,
          borderRight: `1px solid ${colors.border}`,
          boxShadow: shadows.sm,
          zIndex: 10,
          overflowX: 'hidden',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            padding: `0 ${spacing.lg}px`,
            borderBottom: `1px solid ${colors.borderLight}`,
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: radius.md,
              background: colors.brand,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: colors.accent,
              fontWeight: typography.weights.bold,
              fontSize: typography.sizes.lg,
              marginRight: spacing.md,
            }}
          >
            R
          </div>
          <div>
            <div style={{ fontWeight: typography.weights.semibold, fontSize: typography.sizes.base, color: colors.textPrimary }}>
              企业 RAG
            </div>
            <div style={{ fontSize: typography.sizes.xs, color: colors.textMuted }}>私有化多模态</div>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            borderRight: 'none',
            paddingTop: spacing.sm,
          }}
          theme="light"
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: colors.surface,
            padding: `0 ${spacing.lg}px`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: `1px solid ${colors.borderLight}`,
            height: 64,
          }}
        >
          <Typography.Title
            level={4}
            style={{
              margin: 0,
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              color: colors.textPrimary,
              fontSize: typography.sizes.lg,
              fontWeight: typography.weights.semibold,
            }}
          >
            企业级私有化多模态 RAG 系统
          </Typography.Title>
          <Space size={spacing.md} align="center">
            <Badge
              status={systemStatus}
              text={systemStatus === 'success' ? '运行中' : systemStatus === 'warning' ? '服务降级' : '服务异常'}
            />
            <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: colors.textSecondary, fontSize: typography.sizes.base }}>
              {user?.username || 'Admin'}
            </span>
            <Avatar
              style={{
                backgroundColor: colors.accentLight,
                color: colors.accent,
                fontWeight: typography.weights.semibold,
              }}
            >
              {(user?.username || 'A')[0].toUpperCase()}
            </Avatar>
            <Button
              type="link"
              style={{ color: colors.textMuted, padding: 0 }}
              onClick={() => {
                logout()
                navigate('/login')
              }}
            >
              退出
            </Button>
          </Space>
        </Header>
        <Content
          style={{
            margin: spacing.lg,
            padding: spacing.lg,
            background: colors.surface,
            borderRadius: radius.lg,
            minHeight: 280,
            border: `1px solid ${colors.border}`,
            boxShadow: shadows.sm,
            overflowX: 'hidden',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}

export default AppLayout
