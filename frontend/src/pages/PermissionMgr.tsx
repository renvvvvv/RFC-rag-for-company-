import { useEffect, useState } from 'react'
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  message,
  Tag,
  Tabs,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import api from '@/services/api'

const { TabPane } = Tabs
const { Option } = Select

interface SensitiveKeyword {
  id: string
  keyword: string
  level: string
  category?: string
  match_type: string
  variants: string[]
  action: string
  created_at: string
}

interface UserGroup {
  id: string
  name: string
  max_security_level: string
  member_count: number
}

const LEVEL_COLORS: Record<string, string> = {
  L0: 'green',
  L1: 'cyan',
  L2: 'blue',
  L3: 'orange',
  L4: 'red',
}

const PermissionMgr = () => {
  const [keywords, setKeywords] = useState<SensitiveKeyword[]>([])
  const [groups, setGroups] = useState<UserGroup[]>([])
  const [keywordModal, setKeywordModal] = useState(false)
  const [keywordForm] = Form.useForm()

  const fetchKeywords = async () => {
    try {
      const res = await api.get('/v1/keywords')
      setKeywords(res.data)
    } catch (e) {
      message.error('加载关键词失败')
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

  useEffect(() => {
    fetchKeywords()
    fetchGroups()
  }, [])

  const handleCreateKeyword = async (values: any) => {
    try {
      await api.post('/v1/keywords', {
        ...values,
        variants: values.variants ? values.variants.split(',').map((s: string) => s.trim()) : [],
      })
      message.success('创建成功')
      setKeywordModal(false)
      keywordForm.resetFields()
      fetchKeywords()
    } catch (e) {
      message.error('创建失败')
    }
  }

  const keywordColumns = [
    { title: '关键词', dataIndex: 'keyword', key: 'keyword' },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      render: (v: string) => <Tag color={LEVEL_COLORS[v]}>{v}</Tag>,
    },
    { title: '分类', dataIndex: 'category', key: 'category' },
    { title: '匹配方式', dataIndex: 'match_type', key: 'match_type' },
    {
      title: '变体',
      dataIndex: 'variants',
      key: 'variants',
      render: (v: string[]) => v?.join(', '),
    },
    { title: '动作', dataIndex: 'action', key: 'action' },
  ]

  const groupColumns = [
    { title: '群名称', dataIndex: 'name', key: 'name' },
    {
      title: '最高安全级别',
      dataIndex: 'max_security_level',
      key: 'max_security_level',
      render: (v: string) => <Tag color={LEVEL_COLORS[v]}>{v}</Tag>,
    },
    { title: '成员数', dataIndex: 'member_count', key: 'member_count' },
  ]

  return (
    <div>
      <Tabs defaultActiveKey="keywords">
        <TabPane tab="敏感关键词" key="keywords">
          <Card
            title="敏感关键词管理"
            extra={
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setKeywordModal(true)}
              >
                新增关键词
              </Button>
            }
          >
            <Table rowKey="id" dataSource={keywords} columns={keywordColumns} />
          </Card>
        </TabPane>

        <TabPane tab="用户群权限" key="groups">
          <Card title="用户群列表">
            <Table rowKey="id" dataSource={groups} columns={groupColumns} />
          </Card>
        </TabPane>
      </Tabs>

      <Modal
        title="新增敏感关键词"
        open={keywordModal}
        onCancel={() => setKeywordModal(false)}
        onOk={() => keywordForm.submit()}
      >
        <Form form={keywordForm} layout="vertical" onFinish={handleCreateKeyword}>
          <Form.Item
            name="keyword"
            label="关键词"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="level" label="敏感级别" initialValue="L1">
            <Select>
              {['L0', 'L1', 'L2', 'L3', 'L4'].map((l) => (
                <Option key={l} value={l}>
                  {l}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Input placeholder="confidential/privacy/compliance/custom" />
          </Form.Item>
          <Form.Item name="match_type" label="匹配方式" initialValue="exact">
            <Select>
              <Option value="exact">精确</Option>
              <Option value="fuzzy">模糊</Option>
              <Option value="regex">正则</Option>
            </Select>
          </Form.Item>
          <Form.Item name="variants" label="变体（逗号分隔）">
            <Input />
          </Form.Item>
          <Form.Item name="action" label="命中动作" initialValue="audit">
            <Select>
              <Option value="audit">审计</Option>
              <Option value="block">拦截</Option>
              <Option value="mask">脱敏</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default PermissionMgr
