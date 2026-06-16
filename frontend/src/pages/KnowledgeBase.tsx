import { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import api from '@/services/api'

interface KnowledgeBase {
  id: string
  name: string
  description?: string
  status: string
  created_at: string
}

const KnowledgeBase = () => {
  const [data, setData] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [form] = Form.useForm()

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await api.get('/v1/knowledge-bases')
      setData(res.data)
    } catch (e) {
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
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '状态', dataIndex: 'status', key: 'status' },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
  ]

  return (
    <div>
      <Card
        title="知识库管理"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setModalVisible(true)}
          >
            新建知识库
          </Button>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          dataSource={data}
          columns={columns}
        />
      </Card>

      <Modal
        title="新建知识库"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default KnowledgeBase
