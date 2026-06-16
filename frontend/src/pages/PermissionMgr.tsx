import { useEffect, useState } from 'react'
import {
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
  Row,
  Col,
  Typography,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import api from '@/services/api'

import { colors, spacing } from '@/styles/theme'
import PageHeader from '@/components/ui/PageHeader'
import DataCard from '@/components/ui/DataCard'

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
  L0: colors.success,
  L1: colors.info,
  L2: colors.info,
  L3: colors.warning,
  L4: colors.error,
}

const accentButtonStyle = {
  background: colors.accent,
  borderColor: colors.accent,
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

  const renderTargetTypeSelect = () => (
    <Select>
      <Option value="user">用户</Option>
      <Option value="group">用户群</Option>
      <Option value="role">角色</Option>
    </Select>
  )

  const targetTypeField = (
    <Form.Item
      name="target_type"
      label="目标类型"
      initialValue="group"
      rules={[{ required: true }]}
    >
      {renderTargetTypeSelect()}
    </Form.Item>
  )

  const targetIdField = (
    <Form.Item
      name="target_id"
      label="目标ID"
      rules={[{ required: true, message: '请输入目标ID' }]}
    >
      <Input />
    </Form.Item>
  )

  const permissionItems = [
    {
      key: 'document',
      label: '文档权限',
      children: (
        <Form form={docPermForm} layout="vertical" onFinish={handleSetDocumentPermission}>
          <Row gutter={[spacing.lg, spacing.md]}>
            <Col xs={24} md={12}>
              {targetTypeField}
            </Col>
            <Col xs={24} md={12}>
              {targetIdField}
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                name="doc_id"
                label="文档ID"
                rules={[{ required: true, message: '请输入文档ID' }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
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
            </Col>
          </Row>
          <Button
            type="primary"
            htmlType="submit"
            loading={permissionLoading}
            style={accentButtonStyle}
          >
            设置
          </Button>
        </Form>
      ),
    },
    {
      key: 'file-type',
      label: '文件类型权限',
      children: (
        <Form form={fileTypePermForm} layout="vertical" onFinish={handleSetFileTypePermission}>
          <Row gutter={[spacing.lg, spacing.md]}>
            <Col xs={24} md={12}>
              {targetTypeField}
            </Col>
            <Col xs={24} md={12}>
              {targetIdField}
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                name="file_type"
                label="文件类型"
                rules={[{ required: true, message: '请输入文件类型' }]}
              >
                <Input placeholder="例如：pdf, docx, xlsx" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                name="permissions"
                label="权限（逗号分隔）"
                initialValue="READ"
                rules={[{ required: true }]}
              >
                <Input placeholder="例如：READ,WRITE" />
              </Form.Item>
            </Col>
          </Row>
          <Button
            type="primary"
            htmlType="submit"
            loading={permissionLoading}
            style={accentButtonStyle}
          >
            设置
          </Button>
        </Form>
      ),
    },
    {
      key: 'field',
      label: '字段权限',
      children: (
        <Form form={fieldPermForm} layout="vertical" onFinish={handleSetFieldPermission}>
          <Row gutter={[spacing.lg, spacing.md]}>
            <Col xs={24} md={12}>
              {targetTypeField}
            </Col>
            <Col xs={24} md={12}>
              {targetIdField}
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                name="doc_id"
                label="文档ID"
                rules={[{ required: true, message: '请输入文档ID' }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
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
            </Col>
            <Col span={24}>
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
            </Col>
          </Row>
          <Button
            type="primary"
            htmlType="submit"
            loading={permissionLoading}
            style={accentButtonStyle}
          >
            设置
          </Button>
        </Form>
      ),
    },
    {
      key: 'tag',
      label: '标签权限',
      children: (
        <Form form={tagPermForm} layout="vertical" onFinish={handleSetTagPermission}>
          <Row gutter={[spacing.lg, spacing.md]}>
            <Col xs={24} md={12}>
              {targetTypeField}
            </Col>
            <Col xs={24} md={12}>
              {targetIdField}
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="allowed_tags" label="允许标签（逗号分隔）">
                <Input placeholder="例如：公开,内部" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="denied_tags" label="拒绝标签（逗号分隔）">
                <Input placeholder="例如：机密,绝密" />
              </Form.Item>
            </Col>
          </Row>
          <Button
            type="primary"
            htmlType="submit"
            loading={permissionLoading}
            style={accentButtonStyle}
          >
            设置
          </Button>
        </Form>
      ),
    },
    {
      key: 'check',
      label: '权限检查',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Row gutter={[spacing.lg, spacing.md]} align="bottom">
            <Col xs={24} md={12} lg={8}>
              <Input
                placeholder="文档ID"
                value={checkDocId}
                onChange={(e) => setCheckDocId(e.target.value)}
              />
            </Col>
            <Col xs={24} md={12} lg={8}>
              <Button
                type="primary"
                onClick={handleCheckPermission}
                loading={permissionLoading}
                style={accentButtonStyle}
              >
                检查
              </Button>
            </Col>
          </Row>
          {checkResult && (
            <DataCard bodyStyle={{ padding: spacing.md }}>
              <div>
                <Text strong>文档ID：</Text>
                {checkResult.doc_id}
              </div>
              <div>
                <Text strong>权限：</Text>
                <Tag
                  color={
                    checkResult.permission === 'NONE' ? colors.error : colors.success
                  }
                >
                  {checkResult.permission}
                </Tag>
              </div>
              <div>
                <Text strong>安全级别：</Text>
                <Tag color={LEVEL_COLORS[checkResult.security_level]}>
                  {checkResult.security_level}
                </Tag>
              </div>
            </DataCard>
          )}
        </Space>
      ),
    },
  ]

  const mainItems = [
    {
      key: 'keywords',
      label: '敏感关键词',
      children: (
        <DataCard
          title="敏感关键词管理"
          extra={
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setKeywordModal(true)}
              style={accentButtonStyle}
            >
              新增关键词
            </Button>
          }
        >
          <Table rowKey="id" dataSource={keywords} columns={keywordColumns} />
        </DataCard>
      ),
    },
    {
      key: 'groups',
      label: '用户群权限',
      children: (
        <DataCard title="用户群列表">
          <Table rowKey="id" dataSource={groups} columns={groupColumns} />
        </DataCard>
      ),
    },
    {
      key: 'permissions',
      label: '权限设置',
      children: (
        <DataCard title="权限管理">
          <Tabs activeKey={permissionTab} onChange={setPermissionTab} items={permissionItems} />
        </DataCard>
      ),
    },
  ]

  return (
    <div>
      <PageHeader title="权限管理" subtitle="管理敏感关键词、用户群及文档权限配置" />
      <Tabs defaultActiveKey="keywords" items={mainItems} />

      <Modal
        title="新增敏感关键词"
        open={keywordModal}
        onCancel={() => setKeywordModal(false)}
        onOk={() => keywordForm.submit()}
      >
        <Form form={keywordForm} layout="vertical" onFinish={handleCreateKeyword}>
          <Row gutter={[spacing.lg, spacing.md]}>
            <Col xs={24} md={12}>
              <Form.Item name="keyword" label="关键词" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="level" label="敏感级别" initialValue="L1">
                <Select>
                  {['L0', 'L1', 'L2', 'L3', 'L4'].map((l) => (
                    <Option key={l} value={l}>
                      {l}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="category" label="分类">
                <Input placeholder="confidential/privacy/compliance/custom" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="match_type" label="匹配方式" initialValue="exact">
                <Select>
                  <Option value="exact">精确</Option>
                  <Option value="fuzzy">模糊</Option>
                  <Option value="regex">正则</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="variants" label="变体（逗号分隔）">
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="action" label="命中动作" initialValue="audit">
                <Select>
                  <Option value="audit">审计</Option>
                  <Option value="block">拦截</Option>
                  <Option value="mask">脱敏</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </div>
  )
}

export default PermissionMgr
