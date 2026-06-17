import { useEffect, useState } from 'react'
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  message,
  Tabs,
  Alert,
  Row,
  Col,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import api from '@/services/api'
import PageHeader from '@/components/ui/PageHeader'
import DataCard from '@/components/ui/DataCard'
import { colors } from '@/styles/theme'

const { Option } = Select

interface User {
  id: string
  username: string
  email: string
  department?: string
  security_level: string
  status: string
}

interface UserGroup {
  id: string
  name: string
  description?: string
  max_security_level: string
  group_type: string
  member_count: number
}

interface ModelConfig {
  embedding_api_url?: string
  embedding_model: string
  embedding_api_key?: string
  rerank_api_url?: string
  rerank_model: string
  rerank_api_key?: string
  llm_api_url?: string
  llm_model: string
  llm_base_url: string
}

const SystemAdmin = () => {
  const [users, setUsers] = useState<User[]>([])
  const [groups, setGroups] = useState<UserGroup[]>([])
  const [userModal, setUserModal] = useState(false)
  const [groupModal, setGroupModal] = useState(false)
  const [userForm] = Form.useForm()
  const [groupForm] = Form.useForm()

  const [modelConfig, setModelConfig] = useState<ModelConfig | null>(null)
  const [modelForm] = Form.useForm()
  const [savingModel, setSavingModel] = useState(false)

  const fetchUsers = async () => {
    try {
      const res = await api.get('/v1/users')
      setUsers(res.data)
    } catch (e) {
      message.error('加载用户失败')
    }
  }

  const fetchGroups = async () => {
    try {
      const res = await api.get('/v1/groups')
      setGroups(res.data)
    } catch (e) {
      message.error('加载用户群失败')
    }
  }

  const fetchModelConfig = async () => {
    try {
      const res = await api.get('/v1/config/models')
      setModelConfig(res.data)
      modelForm.setFieldsValue(res.data)
    } catch (e) {
      message.error('加载模型配置失败')
    }
  }

  useEffect(() => {
    fetchUsers()
    fetchGroups()
    fetchModelConfig()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleCreateUser = async (values: Record<string, unknown>) => {
    try {
      await api.post('/v1/auth/register', values)
      message.success('用户创建成功')
      setUserModal(false)
      userForm.resetFields()
      fetchUsers()
    } catch (e) {
      message.error('用户创建失败')
    }
  }

  const handleCreateGroup = async (values: Record<string, unknown>) => {
    try {
      await api.post('/v1/groups', values)
      message.success('用户群创建成功')
      setGroupModal(false)
      groupForm.resetFields()
      fetchGroups()
    } catch (e) {
      message.error('用户群创建失败')
    }
  }

  const handleSaveModelConfig = async (values: Record<string, unknown>) => {
    setSavingModel(true)
    try {
      const res = await api.put('/v1/config/models', values)
      message.success(res.data.message)
      fetchModelConfig()
    } catch (e) {
      message.error('保存模型配置失败')
    } finally {
      setSavingModel(false)
    }
  }

  const userColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    { title: '部门', dataIndex: 'department', key: 'department' },
    { title: '安全级别', dataIndex: 'security_level', key: 'security_level' },
    { title: '状态', dataIndex: 'status', key: 'status' },
  ]

  const groupColumns = [
    { title: '群名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '类型', dataIndex: 'group_type', key: 'group_type' },
    { title: '最高级别', dataIndex: 'max_security_level', key: 'max_security_level' },
    { title: '成员数', dataIndex: 'member_count', key: 'member_count' },
  ]

  const accentButtonStyle = { background: colors.accent, borderColor: colors.accent }

  const tabItems = [
    {
      key: 'users',
      label: '用户管理',
      children: (
        <DataCard
          title="用户管理"
          extra={
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setUserModal(true)}
              style={accentButtonStyle}
            >
              新增用户
            </Button>
          }
        >
          <Table rowKey="id" dataSource={users} columns={userColumns} />
        </DataCard>
      ),
    },
    {
      key: 'groups',
      label: '用户群管理',
      children: (
        <DataCard
          title="用户群管理"
          extra={
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setGroupModal(true)}
              style={accentButtonStyle}
            >
              新增用户群
            </Button>
          }
        >
          <Table rowKey="id" dataSource={groups} columns={groupColumns} />
        </DataCard>
      ),
    },
    {
      key: 'models',
      label: '模型配置',
      children: (
        <DataCard title="模型服务配置">
          <Alert
            message="修改后需重启后端服务生效"
            type="info"
            showIcon
            style={{ marginBottom: 16, background: '#eff6ff' }}
          />
          <Form
            form={modelForm}
            layout="vertical"
            onFinish={handleSaveModelConfig}
            initialValues={modelConfig || {}}
          >
            <Row gutter={[24, 0]}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="embedding_api_url"
                  label="Embedding API URL"
                  rules={[{ required: true }]}
                >
                  <Input placeholder="https://yunwu.ai/v1/embeddings" />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  name="embedding_model"
                  label="Embedding 模型名"
                  rules={[{ required: true }]}
                >
                  <Input placeholder="gemini-embedding-2-preview" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={[24, 0]}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="embedding_api_key"
                  label="Embedding API Key"
                >
                  <Input.Password placeholder="sk-xxx" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={[24, 0]}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="rerank_api_url"
                  label="Re-rank API URL"
                  rules={[{ required: true }]}
                >
                  <Input placeholder="https://yunwu.ai/v1/rerank" />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  name="rerank_model"
                  label="Re-rank 模型名"
                  rules={[{ required: true }]}
                >
                  <Input placeholder="qwen3-rerank" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={[24, 0]}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="rerank_api_key"
                  label="Re-rank API Key"
                >
                  <Input.Password placeholder="sk-xxx" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={[24, 0]}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="llm_api_url"
                  label="LLM API URL"
                >
                  <Input placeholder="https://api.minimax.chat/v1/chat/completions" />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  name="llm_model"
                  label="LLM 模型名"
                  rules={[{ required: true }]}
                >
                  <Input placeholder="minimax-m3" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={[24, 0]}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="llm_api_key"
                  label="LLM API Key"
                >
                  <Input.Password placeholder="sk-xxx" />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={savingModel}
                style={accentButtonStyle}
              >
                保存配置
              </Button>
            </Form.Item>
          </Form>
        </DataCard>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="系统管理"
        subtitle="管理用户、用户群和模型服务配置"
      />
      <Tabs defaultActiveKey="users" items={tabItems} />

      <Modal
        title="新增用户"
        open={userModal}
        onCancel={() => setUserModal(false)}
        onOk={() => userForm.submit()}
      >
        <Form form={userForm} layout="vertical" onFinish={handleCreateUser}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="department" label="部门">
            <Input />
          </Form.Item>
          <Form.Item name="security_level" label="安全级别" initialValue="L0">
            <Select>
              {['L0', 'L1', 'L2', 'L3', 'L4'].map((l) => (
                <Option key={l} value={l}>
                  {l}
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="新增用户群"
        open={groupModal}
        onCancel={() => setGroupModal(false)}
        onOk={() => groupForm.submit()}
      >
        <Form form={groupForm} layout="vertical" onFinish={handleCreateGroup}>
          <Form.Item name="name" label="群名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="group_type" label="群类型" initialValue="custom">
            <Select>
              <Option value="department">部门</Option>
              <Option value="project">项目</Option>
              <Option value="custom">自定义</Option>
            </Select>
          </Form.Item>
          <Form.Item name="max_security_level" label="最高安全级别" initialValue="L0">
            <Select>
              {['L0', 'L1', 'L2', 'L3', 'L4'].map((l) => (
                <Option key={l} value={l}>
                  {l}
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default SystemAdmin
