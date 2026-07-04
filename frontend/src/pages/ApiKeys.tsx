import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Checkbox,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import {
  KeyOutlined,
  CopyOutlined,
  DeleteOutlined,
  PlusOutlined,
  EyeInvisibleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import api from '@/services/api'
import { colors, spacing, radius, shadows, typography } from '@/styles/theme'

const { Title, Text, Paragraph } = Typography

interface ApiKey {
  id: string
  owner_id: string
  name: string
  key_prefix: string
  scopes: string[]
  rate_limit_rpm: number
  expires_at: string | null
  last_used_at: string | null
  is_active: boolean
  created_at: string
}

interface ApiKeyCreateResponse extends ApiKey {
  plain_key: string
}

interface ScopesResponse {
  allowed_scopes: string[]
  all_scopes: string[]
}

const SCOPE_LABELS: Record<string, string> = {
  'kb:read': '知识库读取',
  'kb:write': '知识库写入',
  search: '检索',
  chat: '对话',
  'doc:write': '文档写入',
  'user:read': '用户读取',
  'apikey:admin': 'API Key 管理',
  '*': '全部权限',
}

const SCOPE_COLORS: Record<string, string> = {
  'kb:read': colors.info,
  'kb:write': colors.warning,
  search: colors.success,
  chat: '#6654d9',
  'doc:write': colors.accent,
  'user:read': colors.textMuted,
  'apikey:admin': colors.error,
  '*': colors.error,
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return '-'
  return dayjs(iso).format('YYYY-MM-DD HH:mm')
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [scopes, setScopes] = useState<ScopesResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [createdKey, setCreatedKey] = useState<ApiKeyCreateResponse | null>(null)
  const [form] = Form.useForm()

  const fetchKeys = async () => {
    setLoading(true)
    try {
      const res = await api.get<ApiKey[]>('/v1/api-keys')
      setKeys(res.data)
    } catch {
      message.error('获取 API Key 失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchScopes = async () => {
    try {
      const res = await api.get<ScopesResponse>('/v1/api-keys/scopes')
      setScopes(res.data)
    } catch {
      message.error('获取可用权限范围失败')
    }
  }

  useEffect(() => {
    fetchKeys()
    fetchScopes()
  }, [])

  const handleCreate = async (values: {
    name: string
    scopes: string[]
    rate_limit_rpm: number
    expires_at?: dayjs.Dayjs
  }) => {
    setIsSubmitting(true)
    try {
      const payload = {
        name: values.name,
        scopes: values.scopes,
        rate_limit_rpm: values.rate_limit_rpm,
        expires_at: values.expires_at ? values.expires_at.toISOString() : null,
      }
      const res = await api.post<ApiKeyCreateResponse>('/v1/api-keys', payload)
      setCreatedKey(res.data)
      message.success('API Key 创建成功')
      setIsModalOpen(false)
      form.resetFields()
      fetchKeys()
    } catch {
      message.error('创建 API Key 失败')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleRevoke = async (key: ApiKey) => {
    Modal.confirm({
      title: '确认撤销该 API Key？',
      content: `撤销后，使用 "${key.name}" 的外部调用将立即失效。`,
      okText: '撤销',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.delete(`/v1/api-keys/${key.id}`)
          message.success('已撤销')
          fetchKeys()
        } catch {
          message.error('撤销失败')
        }
      },
    })
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      message.success('已复制到剪贴板')
    } catch {
      message.error('复制失败')
    }
  }

  const columns: ColumnsType<ApiKey> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record) => (
        <Space direction="vertical" size={spacing.xs}>
          <Text strong>{name}</Text>
          <Text type="secondary" style={{ fontSize: typography.sizes.xs }}>
            前缀: {record.key_prefix}***
          </Text>
        </Space>
      ),
    },
    {
      title: '权限范围',
      dataIndex: 'scopes',
      key: 'scopes',
      render: (scopes: string[]) => (
        <Space size={spacing.xs} wrap>
          {scopes.map((s) => (
            <Tag key={s} color={SCOPE_COLORS[s] || colors.textMuted}>
              {SCOPE_LABELS[s] || s}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '限流 (RPM)',
      dataIndex: 'rate_limit_rpm',
      key: 'rate_limit_rpm',
      width: 120,
    },
    {
      title: '过期时间',
      dataIndex: 'expires_at',
      key: 'expires_at',
      render: formatDate,
      width: 160,
    },
    {
      title: '最后使用',
      dataIndex: 'last_used_at',
      key: 'last_used_at',
      render: formatDate,
      width: 160,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 90,
      render: (isActive: boolean) =>
        isActive ? <Tag color="success">有效</Tag> : <Tag>已撤销</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_, record) =>
        record.is_active ? (
          <Tooltip title="撤销">
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleRevoke(record)}
            />
          </Tooltip>
        ) : null,
    },
  ]

  const initialScopes = (() => {
    if (!scopes) return []
    if (scopes.allowed_scopes.includes('*')) return ['*']
    return scopes.allowed_scopes.length > 0 ? [scopes.allowed_scopes[0]] : []
  })()

  return (
    <div>
      <Title level={4} style={{ margin: 0, marginBottom: spacing.lg, color: colors.textPrimary }}>
        API Key 管理
      </Title>
      <Paragraph style={{ color: colors.textSecondary, marginBottom: spacing.lg }}>
        创建 API Key 后，外部系统可通过 <Text code>X-API-Key</Text> 或{' '}
        <Text code>Authorization: Bearer {'<key>'}</Text> 调用外部接口。
        Key 的权限继承你的安全等级，无法超出当前账号的权限范围。
      </Paragraph>

      <Card
        style={{
          marginBottom: spacing.lg,
          borderRadius: radius.lg,
          boxShadow: shadows.sm,
        }}
        bodyStyle={{ padding: spacing.lg }}
      >
        <Space style={{ marginBottom: spacing.lg }}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setIsModalOpen(true)}
            style={{ background: colors.accent, borderColor: colors.accent }}
          >
            新建 API Key
          </Button>
        </Space>

        <Table
          rowKey="id"
          columns={columns}
          dataSource={keys}
          loading={loading}
          pagination={{ pageSize: 10 }}
          size="middle"
          bordered
        />
      </Card>

      <Modal
        title="新建 API Key"
        open={isModalOpen}
        onCancel={() => {
          setIsModalOpen(false)
          form.resetFields()
        }}
        footer={null}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{
            rate_limit_rpm: 60,
            scopes: initialScopes,
          }}
        >
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入 API Key 名称' }]}
          >
            <Input placeholder="例如：OA系统集成" maxLength={128} />
          </Form.Item>

          <Form.Item
            name="scopes"
            label="权限范围"
            rules={[{ required: true, message: '请至少选择一个权限范围' }]}
          >
            <Checkbox.Group style={{ width: '100%' }}>
              <Space direction="vertical">
                {scopes?.allowed_scopes.map((s) => (
                  <Checkbox key={s} value={s}>
                    <Tag color={SCOPE_COLORS[s] || colors.textMuted}>
                      {SCOPE_LABELS[s] || s}
                    </Tag>
                  </Checkbox>
                ))}
              </Space>
            </Checkbox.Group>
          </Form.Item>

          <Form.Item
            name="rate_limit_rpm"
            label="每分钟请求上限 (RPM)"
            rules={[{ required: true, message: '请输入限流值' }]}
          >
            <InputNumber min={1} max={10000} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item name="expires_at" label="过期时间（可选）">
            <DatePicker
              showTime
              style={{ width: '100%' }}
              placeholder="不设置则长期有效"
              disabledDate={(current) => current && current < dayjs().startOf('day')}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, marginTop: spacing.lg }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setIsModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={isSubmitting}>
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={
          <Space>
            <KeyOutlined style={{ color: colors.accent }} />
            <span>API Key 创建成功</span>
          </Space>
        }
        open={!!createdKey}
        onCancel={() => setCreatedKey(null)}
        footer={[
          <Button key="close" type="primary" onClick={() => setCreatedKey(null)}>
            我已保存
          </Button>,
        ]}
        closable={false}
        maskClosable={false}
      >
        <Paragraph>
          这是 Key 的明文，只会显示一次，请立即复制并妥善保管：
        </Paragraph>
        <Input.TextArea
          value={createdKey?.plain_key || ''}
          readOnly
          autoSize={{ minRows: 2, maxRows: 4 }}
          style={{
            fontFamily: typography.mono,
            marginBottom: spacing.md,
            background: colors.codeBg,
            color: colors.codeText,
          }}
        />
        <Button
          type="primary"
          icon={<CopyOutlined />}
          onClick={() => createdKey && copyToClipboard(createdKey.plain_key)}
          block
          style={{ marginBottom: spacing.md }}
        >
          复制 Key
        </Button>
        <Paragraph type="secondary" style={{ fontSize: typography.sizes.xs }}>
          <EyeInvisibleOutlined /> 关闭此弹窗后将无法再次查看完整 Key。
        </Paragraph>
      </Modal>
    </div>
  )
}
