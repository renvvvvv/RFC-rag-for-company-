import { useEffect, useState } from 'react'
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Tabs,
  Tag,
  Space,
  message,
  Descriptions,
  Typography,
} from 'antd'
import { PlusOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import api from '@/services/api'

const { TextArea } = Input
const { Option } = Select
const { TabPane } = Tabs
const { Text } = Typography

interface KnowledgeBase {
  id: string
  name: string
}

interface EvaluationDataset {
  id: string
  kb_id: string
  name: string
  questions: string[]
  ground_truths: Record<string, any>[]
  created_at: string
}

interface EvaluationTask {
  id: string
  dataset_id: string
  kb_id: string
  status: string
  metrics: string[]
  results: Record<string, any>
  created_at: string
  completed_at?: string
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
}

const EvalWorkbench = () => {
  const [kbList, setKbList] = useState<KnowledgeBase[]>([])
  const [datasets, setDatasets] = useState<EvaluationDataset[]>([])
  const [tasks, setTasks] = useState<EvaluationTask[]>([])
  const [loadingDatasets, setLoadingDatasets] = useState(false)
  const [loadingTasks, setLoadingTasks] = useState(false)
  const [datasetModalVisible, setDatasetModalVisible] = useState(false)
  const [taskModalVisible, setTaskModalVisible] = useState(false)
  const [selectedTask, setSelectedTask] = useState<EvaluationTask | null>(null)
  const [datasetForm] = Form.useForm()
  const [taskForm] = Form.useForm()

  const fetchKnowledgeBases = async () => {
    try {
      const res = await api.get('/v1/knowledge-bases')
      setKbList(res.data)
    } catch {
      message.error('加载知识库失败')
    }
  }

  const fetchDatasets = async () => {
    setLoadingDatasets(true)
    try {
      const res = await api.get('/v1/evaluation/datasets')
      setDatasets(res.data)
    } catch {
      message.error('加载评测数据集失败')
    } finally {
      setLoadingDatasets(false)
    }
  }

  const fetchTasks = async () => {
    setLoadingTasks(true)
    try {
      const res = await api.get('/v1/evaluation/tasks')
      setTasks(res.data)
    } catch {
      message.error('加载评测任务失败')
    } finally {
      setLoadingTasks(false)
    }
  }

  useEffect(() => {
    fetchKnowledgeBases()
    fetchDatasets()
    fetchTasks()
  }, [])

  const handleCreateDataset = async (values: {
    kb_id: string
    name: string
    questions: string
    ground_truths: string
  }) => {
    try {
      const questions = values.questions
        .split('\n')
        .map((q) => q.trim())
        .filter(Boolean)
      const groundTruths = values.ground_truths
        ? JSON.parse(values.ground_truths)
        : []
      await api.post('/v1/evaluation/datasets', {
        kb_id: values.kb_id,
        name: values.name,
        questions,
        ground_truths: groundTruths,
      })
      message.success('数据集创建成功')
      setDatasetModalVisible(false)
      datasetForm.resetFields()
      fetchDatasets()
    } catch {
      message.error('数据集创建失败')
    }
  }

  const handleCreateTask = async (values: {
    dataset_id: string
    kb_id: string
    metrics: string[]
  }) => {
    try {
      await api.post('/v1/evaluation/tasks', values)
      message.success('评测任务已创建并启动')
      setTaskModalVisible(false)
      taskForm.resetFields()
      fetchTasks()
    } catch {
      message.error('评测任务创建失败')
    }
  }

  const kbName = (id: string) => kbList.find((k) => k.id === id)?.name || id

  const datasetColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '知识库',
      dataIndex: 'kb_id',
      key: 'kb_id',
      render: (v: string) => kbName(v),
    },
    {
      title: '问题数',
      key: 'question_count',
      render: (_: any, record: EvaluationDataset) => record.questions.length,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
  ]

  const taskColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '知识库',
      dataIndex: 'kb_id',
      key: 'kb_id',
      render: (v: string) => kbName(v),
    },
    {
      title: '指标',
      dataIndex: 'metrics',
      key: 'metrics',
      render: (metrics: string[]) => (
        <Space wrap>
          {metrics.map((m) => (
            <Tag key={m}>{m}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: EvaluationTask) => (
        <Button type="link" onClick={() => setSelectedTask(record)}>
          查看结果
        </Button>
      ),
    },
  ]

  const renderAggregatedResults = (task: EvaluationTask) => {
    const aggregated = task.results?.aggregated || {}
    const entries = Object.entries(aggregated).filter(([key]) => key !== 'samples')
    if (entries.length === 0) {
      return <Text type="secondary">暂无结果</Text>
    }
    return (
      <Descriptions bordered column={3}>
        {entries.map(([key, value]) => (
          <Descriptions.Item key={key} label={key}>
            {typeof value === 'number' ? value.toFixed(4) : String(value)}
          </Descriptions.Item>
        ))}
      </Descriptions>
    )
  }

  return (
    <div>
      <Tabs defaultActiveKey="datasets">
        <TabPane tab="评测数据集" key="datasets">
          <Card
            title="评测数据集"
            extra={
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setDatasetModalVisible(true)}
              >
                新建数据集
              </Button>
            }
          >
            <Table
              rowKey="id"
              loading={loadingDatasets}
              dataSource={datasets}
              columns={datasetColumns}
            />
          </Card>
        </TabPane>

        <TabPane tab="评测任务" key="tasks">
          <Card
            title="评测任务"
            extra={
              <Space>
                <Button icon={<ReloadOutlined />} onClick={fetchTasks}>
                  刷新
                </Button>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={() => setTaskModalVisible(true)}
                >
                  运行评测
                </Button>
              </Space>
            }
          >
            <Table
              rowKey="id"
              loading={loadingTasks}
              dataSource={tasks}
              columns={taskColumns}
            />
          </Card>
        </TabPane>
      </Tabs>

      <Modal
        title="新建评测数据集"
        open={datasetModalVisible}
        onCancel={() => setDatasetModalVisible(false)}
        onOk={() => datasetForm.submit()}
      >
        <Form form={datasetForm} layout="vertical" onFinish={handleCreateDataset}>
          <Form.Item
            name="kb_id"
            label="知识库"
            rules={[{ required: true, message: '请选择知识库' }]}
          >
            <Select placeholder="选择知识库">
              {kbList.map((kb) => (
                <Option key={kb.id} value={kb.id}>
                  {kb.name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="name"
            label="数据集名称"
            rules={[{ required: true, message: '请输入数据集名称' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="questions"
            label="问题列表"
            rules={[{ required: true, message: '请输入问题列表' }]}
          >
            <TextArea
              rows={6}
              placeholder="每行一个问题"
            />
          </Form.Item>
          <Form.Item name="ground_truths" label="Ground Truth (JSON)">
            <TextArea
              rows={6}
              placeholder='例如：[{"chunk_ids": ["id1"], "answer": "答案"}]'
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="运行评测"
        open={taskModalVisible}
        onCancel={() => setTaskModalVisible(false)}
        onOk={() => taskForm.submit()}
      >
        <Form form={taskForm} layout="vertical" onFinish={handleCreateTask}>
          <Form.Item
            name="dataset_id"
            label="数据集"
            rules={[{ required: true, message: '请选择数据集' }]}
          >
            <Select placeholder="选择数据集">
              {datasets.map((ds) => (
                <Option key={ds.id} value={ds.id}>
                  {ds.name} ({ds.questions.length} 题)
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="kb_id"
            label="目标知识库"
            rules={[{ required: true, message: '请选择知识库' }]}
          >
            <Select placeholder="选择知识库">
              {kbList.map((kb) => (
                <Option key={kb.id} value={kb.id}>
                  {kb.name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="metrics"
            label="评测指标"
            initialValue={[
              'recall@3',
              'mrr',
              'ndcg@3',
              'faithfulness',
              'relevance',
              'coherence',
            ]}
          >
            <Select mode="multiple" placeholder="选择指标">
              <Option value="recall@3">Recall@3</Option>
              <Option value="mrr">MRR</Option>
              <Option value="ndcg@3">NDCG@3</Option>
              <Option value="faithfulness">Faithfulness</Option>
              <Option value="relevance">Relevance</Option>
              <Option value="coherence">Coherence</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="评测结果"
        open={!!selectedTask}
        onCancel={() => setSelectedTask(null)}
        footer={null}
        width={800}
      >
        {selectedTask && (
          <div>
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLORS[selectedTask.status] || 'default'}>
                  {selectedTask.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="指标">
                {selectedTask.metrics.join(', ')}
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 16 }}>
              <Text strong>聚合指标</Text>
              {renderAggregatedResults(selectedTask)}
            </div>
            {selectedTask.results?.aggregated?.samples && (
              <div style={{ marginTop: 16 }}>
                <Text strong>样本详情</Text>
                <pre style={{ maxHeight: 300, overflow: 'auto', background: '#f6f6f6', padding: 12 }}>
                  {JSON.stringify(selectedTask.results.aggregated.samples, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}

export default EvalWorkbench
