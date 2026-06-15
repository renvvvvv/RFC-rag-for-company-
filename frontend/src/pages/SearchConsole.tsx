import { useEffect, useState, useRef } from 'react'
import {
  Card,
  Input,
  Button,
  Select,
  Tag,
  List,
  Typography,
  Space,
  message,
  Checkbox,
  Spin,
} from 'antd'
import { SendOutlined } from '@ant-design/icons'
import api from '@/services/api'

const { TextArea } = Input
const { Option } = Select
const { Text, Paragraph } = Typography

interface KnowledgeBase {
  id: string
  name: string
}

interface Source {
  doc_id: string
  chunk_id: string
  content: string
  score: number
  modality: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  intercepted?: boolean
  strategy?: {
    strategy: string
    max_level: number
    reason: string
  }
}

const MODALITY_OPTIONS = [
  { label: '文档', value: 'text' },
  { label: '表格', value: 'table' },
  { label: '图片', value: 'image' },
  { label: '链接', value: 'link' },
]

const SearchConsole = () => {
  const [kbList, setKbList] = useState<KnowledgeBase[]>([])
  const [selectedKbs, setSelectedKbs] = useState<string[]>([])
  const [modalities, setModalities] = useState<string[]>(['text', 'table', 'link'])
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api
      .get('/v1/knowledge-bases')
      .then((res) => {
        setKbList(res.data)
      })
      .catch(() => message.error('加载知识库失败'))
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!query.trim()) return
    if (selectedKbs.length === 0) {
      message.warning('请至少选择一个知识库')
      return
    }

    const userMsg: ChatMessage = { role: 'user', content: query }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    const currentQuery = query
    setQuery('')

    try {
      const res = await api.post('/v1/chat', {
        query: currentQuery,
        kb_ids: selectedKbs,
        modalities,
        top_k: 10,
        rerank_top_k: 5,
      })
      const data = res.data
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources,
          intercepted: data.intercepted,
          strategy: data.strategy,
        },
      ])
    } catch (e) {
      message.error('请求失败')
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '请求处理失败，请稍后重试。',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 180px)' }}>
      <Card title="检索配置" style={{ width: 320, flexShrink: 0 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>知识库</Text>
            <Select
              mode="multiple"
              style={{ width: '100%', marginTop: 8 }}
              placeholder="选择知识库"
              value={selectedKbs}
              onChange={setSelectedKbs}
            >
              {kbList.map((kb) => (
                <Option key={kb.id} value={kb.id}>
                  {kb.name}
                </Option>
              ))}
            </Select>
          </div>
          <div>
            <Text strong>模态</Text>
            <Checkbox.Group
              style={{ marginTop: 8, display: 'block' }}
              options={MODALITY_OPTIONS}
              value={modalities}
              onChange={(vals) => setModalities(vals as string[])}
            />
          </div>
        </Space>
      </Card>

      <Card title="检索问答" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflowY: 'auto', marginBottom: 16, paddingRight: 8 }}>
          {messages.length === 0 && (
            <div style={{ color: '#999', textAlign: 'center', marginTop: 100 }}>
              输入问题开始检索企业知识库
            </div>
          )}
          <List
            dataSource={messages}
            renderItem={(msg, idx) => (
              <List.Item
                key={idx}
                style={{
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '80%',
                    background: msg.role === 'user' ? '#1677ff' : '#f6f6f6',
                    color: msg.role === 'user' ? '#fff' : '#333',
                    padding: 12,
                    borderRadius: 8,
                  }}
                >
                  <Paragraph style={{ margin: 0, color: 'inherit' }}>
                    {msg.content}
                  </Paragraph>
                  {msg.intercepted && (
                    <Tag color="red" style={{ marginTop: 8 }}>
                      已拦截
                    </Tag>
                  )}
                  {msg.strategy && (
                    <Tag color="blue" style={{ marginTop: 8 }}>
                      {msg.strategy.strategy}: {msg.strategy.reason}
                    </Tag>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <Text strong style={{ color: 'inherit' }}>
                        来源：
                      </Text>
                      {msg.sources.map((s, i) => (
                        <Tag key={i} color="default">
                          {s.modality} [{s.score.toFixed(2)}]
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>
              </List.Item>
            )}
          />
          {loading && (
            <div style={{ textAlign: 'center', padding: 16 }}>
              <Spin tip="检索生成中..." />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入您的问题..."
            autoSize={{ minRows: 2, maxRows: 6 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            style={{ height: 'auto' }}
          >
            发送
          </Button>
        </Space.Compact>
      </Card>
    </div>
  )
}

export default SearchConsole
