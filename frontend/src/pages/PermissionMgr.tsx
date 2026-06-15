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
  Space,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import api from '@/services/api'

import { Typography } from 'antd'

const { TabPane } = Tabs
const { Option } = Select
const { Text } = Typography

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

  // Permission forms state
  const [permissionTab, setPermissionTab] = useState('document')
  const [checkDocId, setCheckDocId] = useState('')
  const [checkResult, setCheckResult] = useState<{
    doc_id: string
    permission: string
    security_level: string
  } | null>(null)
  const [permissionLoading, setPermissionLoading] = useState(false)

  const [docPermForm] = Form.useForm()
  const [fileTypePermForm] = Form.useForm()
  const [fieldPermForm] = Form.useForm()
  const [tagPermForm] = Form.useForm()

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

  const handleCreateKeyword = async (
    values: Record<string, unknown> & { variants?: string }
  ) => {
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

  const handleSetDocumentPermission = async (values: {
    target_type: string
    target_id: string
    doc_id: string
    permission: string
  }) => {
    setPermissionLoading(true)
    try {
      await api.post('/v1/permissions/document', values)
      message.success('文档权限设置成功')
      docPermForm.resetFields()
    } catch (e) {
      message.error('文档权限设置失败')
    } finally {
      setPermissionLoading(false)
    }
  }

  const handleSetFileTypePermission = async (values: {
    target_type: string
    target_id: string
    file_type: string
    permissions: string
  }) => {
    setPermissionLoading(true)
    try {
      await api.post('/v1/permissions/file-type', {
        target_type: values.target_type,
        target_id: values.target_id,
        file_type: values.file_type,
        permissions: values.permissions.split(',').map((s: string) => s.trim()),
      })
      message.success('文件类型权限设置成功')
      fileTypePermForm.resetFields()
    } catch (e) {
      message.error('文件类型权限设置失败')
    } finally {
      setPermissionLoading(false)
    }
  }

  const handleSetFieldPermission = async (values: {
    target_type: string
    target_id: string
    doc_id: string
    file_type: string
    config_json: string
  }) => {
    setPermissionLoading(true)
    try {
      const config = values.config_json ? JSON.parse(values.config_json) : {}
      await api.post('/v1/permissions/field', {
        target_type: values.target_type,
        target_id: values.target_id,
        doc_id: values.doc_id,
        file_type: values.file_type,
        word_config: config.word_config,
        excel_config: config.excel_config,
      })
      message.success('字段权限设置成功')
      fieldPermForm.resetFields()
    } catch (e) {
      message.error('字段权限设置失败，请检查 JSON 格式')
    } finally {
      setPermissionLoading(false)
    }
  }

  const handleSetTagPermission = async (values: {
    target_type: string
    target_id: string
    allowed_tags: string
    denied_tags: string
  }) => {
    setPermissionLoading(true)
    try {
      await api.post('/v1/permissions/tag', {
        target_type: values.target_type,
        target_id: values.target_id,
        allowed_tags: values.allowed_tags
          ? values.allowed_tags.split(',').map((s: string) => s.trim())
          : [],
        denied_tags: values.denied_tags
          ? values.denied_tags.split(',').map((s: string) => s.trim())
          : [],
      })
      message.success('标签权限设置成功')
      tagPermForm.resetFields()
    } catch (e) {
      message.error('标签权限设置失败')
    } finally {
      setPermissionLoading(false)
    }
  }

  const handleCheckPermission = async () => {
    if (!checkDocId) {
      message.warning('请输入文档ID')
      return
    }
    setPermissionLoading(true)
    try {
      const res = await api.get(`/v1/permissions/check/${checkDocId}`)
      setCheckResult(res.data)
    } catch (e) {
      message.error('权限检查失败')
    } finally {
      setPermissionLoading(false)
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

        <TabPane tab="权限设置" key="permissions">
          <Card title="权限管理">
            <Tabs activeKey={permissionTab} onChange={setPermissionTab}>
              <TabPane tab="文档权限" key="document">
                <Form
                  form={docPermForm}
                  layout="vertical"
                  onFinish={handleSetDocumentPermission}
                >
                  <Form.Item
                    name="target_type"
                    label="目标类型"
                    initialValue="group"
                    rules={[{ required: true }]}
                  >
                    <Select>
                      <Option value="user">用户</Option>
                      <Option value="group">用户群</Option>
                      <Option value="role">角色</Option>
                    </Select>
                  </Form.Item>
                  <Form.Item
                    name="target_id"
                    label="目标ID"
                    rules={[{ required: true, message: '请输入目标ID' }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="doc_id"
                    label="文档ID"
                    rules={[{ required: true, message: '请输入文档ID' }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="permission"
                    label="权限"
                    initialValue="READ"
                    rules={[{ required: true }]}
                  >
                    <Select>
                      <Option value="NONE">无</Option>
                      <Option value="READ">读</Option>
                      <Option value="WRITE">写</Option>
                      <Option value="ADMIN">管理</Option>
                    </Select>
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={permissionLoading}>
                    设置
                  </Button>
                </Form>
              </TabPane>

              <TabPane tab="文件类型权限" key="file-type">
                <Form
                  form={fileTypePermForm}
                  layout="vertical"
                  onFinish={handleSetFileTypePermission}
                >
                  <Form.Item
                    name="target_type"
                    label="目标类型"
                    initialValue="group"
                    rules={[{ required: true }]}
                  >
                    <Select>
                      <Option value="user">用户</Option>
                      <Option value="group">用户群</Option>
                      <Option value="role">角色</Option>
                    </Select>
                  </Form.Item>
                  <Form.Item
                    name="target_id"
                    label="目标ID"
                    rules={[{ required: true, message: '请输入目标ID' }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="file_type"
                    label="文件类型"
                    rules={[{ required: true, message: '请输入文件类型' }]}
                  >
                    <Input placeholder="例如：pdf, docx, xlsx" />
                  </Form.Item>
                  <Form.Item
                    name="permissions"
                    label="权限（逗号分隔）"
                    initialValue="READ"
                    rules={[{ required: true }]}
                  >
                    <Input placeholder="例如：READ,WRITE" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={permissionLoading}>
                    设置
                  </Button>
                </Form>
              </TabPane>

              <TabPane tab="字段权限" key="field">
                <Form
                  form={fieldPermForm}
                  layout="vertical"
                  onFinish={handleSetFieldPermission}
                >
                  <Form.Item
                    name="target_type"
                    label="目标类型"
                    initialValue="group"
                    rules={[{ required: true }]}
                  >
                    <Select>
                      <Option value="user">用户</Option>
                      <Option value="group">用户群</Option>
                      <Option value="role">角色</Option>
                    </Select>
                  </Form.Item>
                  <Form.Item
                    name="target_id"
                    label="目标ID"
                    rules={[{ required: true, message: '请输入目标ID' }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="doc_id"
                    label="文档ID"
                    rules={[{ required: true, message: '请输入文档ID' }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="file_type"
                    label="文件类型"
                    initialValue="word"
                    rules={[{ required: true }]}
                  >
                    <Select>
                      <Option value="word">Word</Option>
                      <Option value="excel">Excel</Option>
                    </Select>
                  </Form.Item>
                  <Form.Item
                    name="config_json"
                    label="配置 JSON"
                    rules={[{ required: true, message: '请输入配置 JSON' }]}
                  >
                    <Input.TextArea
                      rows={5}
                      placeholder='{"word_config": {...}, "excel_config": {...}}'
                    />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={permissionLoading}>
                    设置
                  </Button>
                </Form>
              </TabPane>

              <TabPane tab="标签权限" key="tag">
                <Form
                  form={tagPermForm}
                  layout="vertical"
                  onFinish={handleSetTagPermission}
                >
                  <Form.Item
                    name="target_type"
                    label="目标类型"
                    initialValue="group"
                    rules={[{ required: true }]}
                  >
                    <Select>
                      <Option value="user">用户</Option>
                      <Option value="group">用户群</Option>
                      <Option value="role">角色</Option>
                    </Select>
                  </Form.Item>
                  <Form.Item
                    name="target_id"
                    label="目标ID"
                    rules={[{ required: true, message: '请输入目标ID' }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item name="allowed_tags" label="允许标签（逗号分隔）">
                    <Input placeholder="例如：公开,内部" />
                  </Form.Item>
                  <Form.Item name="denied_tags" label="拒绝标签（逗号分隔）">
                    <Input placeholder="例如：机密,绝密" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={permissionLoading}>
                    设置
                  </Button>
                </Form>
              </TabPane>

              <TabPane tab="权限检查" key="check">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Input
                    placeholder="文档ID"
                    value={checkDocId}
                    onChange={(e) => setCheckDocId(e.target.value)}
                  />
                  <Button type="primary" onClick={handleCheckPermission} loading={permissionLoading}>
                    检查
                  </Button>
                  {checkResult && (
                    <Card size="small">
                      <div>
                        <Text strong>文档ID：</Text>
                        {checkResult.doc_id}
                      </div>
                      <div>
                        <Text strong>权限：</Text>
                        <Tag color={checkResult.permission === 'NONE' ? 'red' : 'green'}>
                          {checkResult.permission}
                        </Tag>
                      </div>
                      <div>
                        <Text strong>安全级别：</Text>
                        <Tag color={LEVEL_COLORS[checkResult.security_level]}>
                          {checkResult.security_level}
                        </Tag>
                      </div>
                    </Card>
                  )}
                </Space>
              </TabPane>
            </Tabs>
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
          <Form.Item name="keyword" label="关键词" rules={[{ required: true }]}>
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
