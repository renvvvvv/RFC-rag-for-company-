import { useEffect, useState } from 'react'
import { Table, Button, Modal, Form, Input, Tag, Space, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import api from '@/services/api'
import PageHeader from '@/components/ui/PageHeader'
import DataCard from '@/components/ui/DataCard'
import LoadingState from '@/components/ui/LoadingState'
import EmptyState from '@/components/ui/EmptyState'
import ErrorState from '@/components/ui/ErrorState'
import { colors, radius } from '@/styles/theme'

interface KnowledgeBase {
  id: string
  name: string
  description?: string
  status: string
  created_at: string
}

const statusMap: Record<string, { label: string; color: string }> = {
  active: { label: '可用', color: colors.success },
  processing: { label: '处理中', color: colors.warning },
  error: { label: '异常', color: colors.error },
  inactive: { label: '停用', color: colors.textMuted },
}

const KnowledgeBase = () => {
  const [data, setData] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [form] = Form.useForm()

  const fetchData = async () => {
    setLoading(true)
    setError(false)
    try {
      const res = await api.get('/v1/knowledge-bases')
      setData(res.data)
    } catch (e) {
      setError(true)
      message.error('加载知识库失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleCreate = async (values: { name: string; description: string }) => {
    try {
      await api.post('/v1/knowledge-bases', values)
      message.success('创建成功')
      setModalVisible(false)
      form.resetFields()
      fetchData()
    } catch (e) {
      message.error('创建失败')
    }
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 220 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (v: string) => {
        const meta = statusMap[v] || { label: v, color: colors.textMuted }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString(),
    },
  ]

  if (loading && data.length === 0) return <LoadingState fullHeight tip="正在加载知识库..." />
  if (error && data.length === 0) return <ErrorState title="加载失败" subTitle="无法获取知识库列表" onRetry={fetchData} />

  return (
    <div>
      <PageHeader
        title="知识库管理"
        subtitle="管理企业私有知识库，为检索与问答提供数据基础。"
      />

      <DataCard
        title={
          <Space>
            <span>知识库列表</span>
            <Tag color={colors.accent}>{data.length}</Tag>
          </Space>
        }
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setModalVisible(true)}
            style={{ background: colors.accent, borderColor: colors.accent, borderRadius: radius.md }}
          >
            新建知识库
          </Button>
        }
      >
        {data.length === 0 ? (
          <EmptyState
            description="暂无知识库"
            subDescription="点击右上角按钮创建第一个知识库"
          />
        ) : (
          <Table
            rowKey="id"
            loading={loading}
            dataSource={data}
            columns={columns}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
          />
        )}
      </DataCard>

      <Modal
        title="新建知识库"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        okButtonProps={{ style: { background: colors.accent, borderColor: colors.accent } }}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="例如：产品手册知识库" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="简要描述知识库用途" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default KnowledgeBase
