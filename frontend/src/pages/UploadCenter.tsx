import { useEffect, useState } from 'react'
import {
  Upload,
  Button,
  Form,
  Input,
  Select,
  message,
  Tag,
  Space,
  Tabs,
  Table,
} from 'antd'
import {
  InboxOutlined,
  LinkOutlined,
  FilePdfOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileTextOutlined,
  VideoCameraOutlined,
  AudioOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons'
import type { UploadFile, UploadProps } from 'antd/es/upload'
import api from '@/services/api'
import PageHeader from '@/components/ui/PageHeader'
import DataCard from '@/components/ui/DataCard'
import EmptyState from '@/components/ui/EmptyState'
import { colors, radius, spacing, typography } from '@/styles/theme'

const { Dragger } = Upload
const { Option } = Select

interface KnowledgeBase {
  id: string
  name: string
}

interface DocumentItem {
  id: string
  filename: string
  file_type: string
  status: string
  created_at: string
}

const FILE_ICONS: Record<string, React.ReactNode> = {
  pdf: <FilePdfOutlined style={{ color: colors.error }} />,
  excel: <FileExcelOutlined style={{ color: colors.success }} />,
  image: <FileImageOutlined style={{ color: colors.info }} />,
  video: <VideoCameraOutlined style={{ color: colors.warning }} />,
  audio: <AudioOutlined style={{ color: colors.accent }} />,
  document: <FileTextOutlined style={{ color: colors.textSecondary }} />,
}

const statusMap: Record<string, { label: string; color: string }> = {
  indexed: { label: '已索引', color: colors.success },
  active: { label: '可用', color: colors.success },
  processing: { label: '处理中', color: colors.warning },
  failed: { label: '失败', color: colors.error },
  pending: { label: '待处理', color: colors.info },
}

const UploadCenter = () => {
  const [kbList, setKbList] = useState<KnowledgeBase[]>([])
  const [selectedKb, setSelectedKb] = useState<string>()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [docsLoading, setDocsLoading] = useState(false)
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [linkForm] = Form.useForm()

  const fetchKBs = async () => {
    try {
      const res = await api.get('/v1/knowledge-bases')
      setKbList(res.data)
      if (res.data.length > 0 && !selectedKb) {
        setSelectedKb(res.data[0].id)
      }
    } catch (e) {
      message.error('加载知识库失败')
    }
  }

  const fetchDocs = async () => {
    if (!selectedKb) return
    setDocsLoading(true)
    try {
      const res = await api.get(`/v1/documents/${selectedKb}`)
      setDocs(res.data.items || [])
    } catch (e) {
      message.error('加载文档失败')
    } finally {
      setDocsLoading(false)
    }
  }

  useEffect(() => {
    fetchKBs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    fetchDocs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKb])

  const customUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options
    if (!selectedKb) {
      message.error('请先选择知识库')
      onError?.(new Error('No KB selected'))
      return
    }

    const formData = new FormData()
    formData.append('file', file)
    formData.append('kb_id', selectedKb)
    formData.append('title', (file as File).name)

    try {
      await api.post('/v1/documents', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      onSuccess?.('ok')
      message.success(`${(file as File).name} 上传成功`)
      fetchDocs()
    } catch (e) {
      onError?.(new Error('Upload failed'))
      message.error(`${(file as File).name} 上传失败`)
    }
  }

  const handleLinkSubmit = async (values: { url: string; tags?: string }) => {
    if (!selectedKb) {
      message.error('请先选择知识库')
      return
    }
    try {
      await api.post('/v1/documents/link', {
        kb_id: selectedKb,
        ...values,
        metadata: { title: values.url },
      })
      message.success('链接提交成功')
      linkForm.resetFields()
      fetchDocs()
    } catch (e) {
      message.error('链接提交失败')
    }
  }

  const docColumns = [
    {
      title: '文件名 / URL',
      dataIndex: 'filename',
      key: 'filename',
      render: (v: string, record: DocumentItem) => (
        <Space>
          {FILE_ICONS[record.file_type] || <FileTextOutlined style={{ color: colors.textSecondary }} />}
          <span style={{ color: colors.textPrimary }}>{v}</span>
        </Space>
      ),
    },
    { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 100 },
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

  const tabItems = [
    {
      key: 'file',
      label: (
        <Space>
          <CloudUploadOutlined />
          <span>文件上传</span>
        </Space>
      ),
      children: (
        <Dragger
          customRequest={customUpload}
          fileList={fileList}
          onChange={({ fileList: next }) => setFileList(next)}
          multiple
          accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg,.gif,.mp4,.avi,.mov,.mp3,.wav,.txt,.md"
          style={{
            padding: spacing.xl,
            borderRadius: radius.lg,
            background: colors.surfaceAlt,
            border: `1px dashed ${colors.border}`,
          }}
        >
          <p style={{ fontSize: 40, color: colors.accent, marginBottom: spacing.md }}>
            <InboxOutlined />
          </p>
          <p style={{ fontSize: typography.sizes.md, color: colors.textPrimary, marginBottom: spacing.sm }}>
            点击或拖拽文件到此区域上传
          </p>
          <p style={{ color: colors.textMuted, fontSize: typography.sizes.sm }}>
            支持 PDF / Word / Excel / 图片 / 视频 / 音频 / 文本 / Markdown
          </p>
        </Dragger>
      ),
    },
    {
      key: 'link',
      label: (
        <Space>
          <LinkOutlined />
          <span>链接上传</span>
        </Space>
      ),
      children: (
        <Form form={linkForm} layout="vertical" onFinish={handleLinkSubmit}>
          <Form.Item
            name="url"
            label="网页链接"
            rules={[{ required: true, type: 'url', message: '请输入有效URL' }]}
          >
            <Input prefix={<LinkOutlined />} placeholder="https://..." />
          </Form.Item>
          <Form.Item name="tags" label="标签（逗号分隔）">
            <Input placeholder="标签1,标签2" />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              style={{ background: colors.accent, borderColor: colors.accent, borderRadius: radius.md }}
            >
              提交链接
            </Button>
          </Form.Item>
        </Form>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="上传中心"
        subtitle="将文件或网页链接上传到指定知识库，支持多模态内容解析与索引。"
      />

      <DataCard
        title="上传文档"
        extra={
          <Space>
            <span style={{ color: colors.textSecondary, fontSize: typography.sizes.sm }}>目标知识库</span>
            <Select
              style={{ width: 240 }}
              value={selectedKb}
              onChange={setSelectedKb}
              placeholder="请选择知识库"
            >
              {kbList.map((kb) => (
                <Option key={kb.id} value={kb.id}>
                  {kb.name}
                </Option>
              ))}
            </Select>
          </Space>
        }
        style={{ marginBottom: spacing.lg }}
      >
        <Tabs defaultActiveKey="file" items={tabItems} />
      </DataCard>

      <DataCard
        title={
          <Space>
            <span>文档列表</span>
            <Tag color={colors.accent}>{docs.length}</Tag>
          </Space>
        }
      >
        {docs.length === 0 && !docsLoading ? (
          <EmptyState
            description="暂无文档"
            subDescription="上传文件或提交链接后，文档将显示在这里"
          />
        ) : (
          <Table
            rowKey="id"
            dataSource={docs}
            columns={docColumns}
            loading={docsLoading}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
          />
        )}
      </DataCard>
    </div>
  )
}

export default UploadCenter
