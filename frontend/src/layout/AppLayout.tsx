import type React from 'react'
import { Layout, Menu, Avatar, Space, Typography, Button } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  DatabaseOutlined,
  UploadOutlined,
  SearchOutlined,
  LineChartOutlined,
  SafetyOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/authStore'

const { Header, Sider, Content } = Layout

interface AppLayoutProps {
  children: React.ReactNode
}

const menuItems = [
  { key: '/', icon: <DatabaseOutlined />, label: '知识库' },
  { key: '/upload-center', icon: <UploadOutlined />, label: '上传中心' },
  { key: '/search-console', icon: <SearchOutlined />, label: '检索控制台' },
  { key: '/eval-workbench', icon: <LineChartOutlined />, label: '评测工作台' },
  { key: '/permission-mgr', icon: <SafetyOutlined />, label: '权限管理' },
  { key: '/system-admin', icon: <SettingOutlined />, label: '系统管理' },
]

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light" width={220}>
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            fontSize: 16,
          }}
        >
          企业 RAG
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Typography.Title level={4} style={{ margin: 0 }}>
            企业级私有化多模态 RAG 系统
          </Typography.Title>
          <Space>
            <span>{user?.username || 'Admin'}</span>
            <Avatar style={{ backgroundColor: '#1677ff' }}>
              {(user?.username || 'A')[0].toUpperCase()}
            </Avatar>
            <Button type="link" onClick={() => { logout(); navigate('/login') }}>
              退出
            </Button>
          </Space>
        </Header>
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: '#fff',
            borderRadius: 8,
            minHeight: 280,
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}

export default AppLayout
