import { useEffect, useState } from 'react'
import {
  Card,
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
} from '@ant-design/icons'
import type { UploadFile, UploadProps } from 'antd/es/upload'
import api from '@/services/api'

const { Dragger } = Upload
const { TabPane } = Tabs
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
  pdf: <FilePdfOutlined />,
  excel: <FileExcelOutlined />,
  image: <FileImageOutlined />,
  video: <VideoCameraOutlined />,
  audio: <AudioOutlined />,
  document: <FileTextOutlined />,
}

const UploadCenter = () => {
  const [kbList, setKbList] = useState<KnowledgeBase[]>([])
  const [selectedKb, setSelectedKb] = useState<string>()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [loading] = useState(false)
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
    try {
      const res = await api.get(`/v1/documents/${selectedKb}`)
      setDocs(res.data.items || [])
    } catch (e) {
      message.error('加载文档失败')
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
      await api.post('/v1/documents/', formData, {
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
      title: '文件名/URL',
      dataIndex: 'filename',
      key: 'filename',
      render: (v: string, record: DocumentItem) => (
        <Space>
          {FILE_ICONS[record.file_type] || <FileTextOutlined />}
          {v}
        </Space>
      ),
    },
    { title: '类型', dataIndex: 'file_type', key: 'file_type' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => {
        const color =
          v === 'indexed' || v === 'active' ? 'green' : v === 'failed' ? 'red' : 'processing'
        return <Tag color={color}>{v}</Tag>
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
  ]

  return (
    <div>
      <Card title="上传中心" style={{ marginBottom: 24 }}>
        <Space style={{ marginBottom: 16 }}>
          <span>选择知识库：</span>
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

        <Tabs defaultActiveKey="file">
          <TabPane tab="文件上传" key="file">
            <Dragger
              customRequest={customUpload}
              fileList={fileList}
              onChange={({ fileList }) => setFileList(fileList)}
              multiple
              accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg,.gif,.mp4,.avi,.mov,.mp3,.wav,.txt,.md"
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                支持 PDF / Word / Excel / 图片 / 视频 / 音频 / 文本 / Markdown
              </p>
            </Dragger>
          </TabPane>

          <TabPane tab="链接上传" key="link">
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
                <Button type="primary" htmlType="submit">
                  提交链接
                </Button>
              </Form.Item>
            </Form>
          </TabPane>
        </Tabs>
      </Card>

      <Card title="文档列表">
        <Table rowKey="id" dataSource={docs} columns={docColumns} loading={loading} />
      </Card>
    </div>
  )
}

export default UploadCenter
