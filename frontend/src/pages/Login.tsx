import { useState } from 'react'
import { Card, Form, Input, Button, message, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'

const { Title } = Typography

interface LoginForm {
  username: string
  password: string
}

const Login = () => {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { setToken, setUser } = useAuthStore()

  const handleLogin = async (values: LoginForm) => {
    setLoading(true)
    try {
      const res = await api.post('/v1/auth/login', new URLSearchParams({
        username: values.username,
        password: values.password,
      }), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      const { access_token, user } = res.data
      setToken(access_token)
      setUser(user)
      message.success('登录成功')
      navigate('/')
    } catch (e: any) {
      message.error(e.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: '#f0f2f5',
      }}
    >
      <Card style={{ width: 400 }}>
        <Title level={3} style={{ textAlign: 'center' }}>
          企业级私有 RAG
        </Title>
        <Form layout="vertical" onFinish={handleLogin}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="admin" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password placeholder="admin123" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default Login
