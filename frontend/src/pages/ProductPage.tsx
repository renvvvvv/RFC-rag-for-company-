import { useState } from 'react'
import {
  Typography,
  Card,
  Row,
  Col,
  Tabs,
  Steps,
  Descriptions,
  Alert,
  Space,
  Tag,
  Divider,
  Button,
  Collapse,
} from 'antd'
import {
  LockOutlined,
  SafetyOutlined,
  ApiOutlined,
  CloudServerOutlined,
  SearchOutlined,
  FileTextOutlined,
  TeamOutlined,
  KeyOutlined,
  GlobalOutlined,
} from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography
const { Step } = Steps
const { Panel } = Collapse

const painPoints = [
  {
    title: '数据孤岛与知识分散',
    desc: '企业文档、图纸、音视频、数据库记录分散在多个业务系统中，传统搜索无法跨模态、跨系统统一检索，导致员工找不到、找不准所需知识。',
    icon: <SearchOutlined style={{ fontSize: 28, color: '#1677ff' }} />,
  },
  {
    title: '私有化部署与数据安全',
    desc: '金融、制造、政务等行业对数据出境和云端 SaaS 有严格限制，需要可私有化部署、数据不出域的 RAG 方案，同时满足审计与合规要求。',
    icon: <SafetyOutlined style={{ fontSize: 28, color: '#52c41a' }} />,
  },
  {
    title: '细粒度权限管控缺失',
    desc: '通用 RAG 往往忽略企业已有 ACL，出现低权限用户检索到高密级内容、不同部门看到不该看的文档等安全隐患。',
    icon: <LockOutlined style={{ fontSize: 28, color: '#faad14' }} />,
  },
  {
    title: '多模态内容理解困难',
    desc: '合同、报表、设计图、培训视频等非结构化数据难以被 LLM 直接理解，需要统一的多模态解析、 embedding、索引与检索能力。',
    icon: <FileTextOutlined style={{ fontSize: 28, color: '#722ed1' }} />,
  },
  {
    title: '外部系统集成复杂',
    desc: '企业 OA、IM、ERP、BI 等系统希望调用 RAG 能力，但缺乏标准、安全、可审计的 API 接入方案，导致重复开发和对接成本高昂。',
    icon: <ApiOutlined style={{ fontSize: 28, color: '#eb2f96' }} />,
  },
]

const permissionLayers = [
  {
    title: '身份层',
    items: ['用户 / 用户组管理', 'JWT 登录与令牌刷新', '部门、职级、安全等级属性'],
  },
  {
    title: '知识库层',
    items: ['知识库可见性控制', '按用户组授权读写', '目录级访问策略'],
  },
  {
    title: '文档层',
    items: ['文档级 ACL（允许/拒绝列表）', '按用户/用户组授权', '密级标签匹配'],
  },
  {
    title: '字段/文件类型层',
    items: ['按文件类型（Word/Excel/PDF）授权', '按字段配置（如 salary、id_card）脱敏或拒绝'],
  },
  {
    title: '标签层',
    items: ['多维度标签（密级、部门、项目）', '标签批量授权与回收', '检索时动态过滤'],
  },
]

const ragSteps = [
  { title: '多模态接入', desc: '支持 Word、Excel、PPT、PDF、图片、音视频、网页链接等统一上传' },
  { title: '解析与分块', desc: 'OCR、ASR、表格提取、文档结构解析，生成文本/图像/音频 Chunk' },
  { title: '向量化索引', desc: '多模态 Embedding 模型生成稠密向量，写入 Milvus 向量数据库' },
  { title: '混合检索', desc: '向量相似度 + BM25 + 重排序（Rerank），召回高相关片段' },
  { title: '权限过滤', desc: '检索结果经统一权限服务过滤，确保用户只能看到授权内容' },
  { title: 'LLM 生成', desc: '带引用溯源的生成，支持流式输出与敏感词拦截' },
]

const externalAuthTabs = [
  {
    key: 'kong',
    label: 'Kong 网关接入',
    icon: <GlobalOutlined />,
    content: (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Paragraph>
          系统使用 Kong 作为统一入口，所有外部流量先经过 Kong 再路由到前端或后端服务。
        </Paragraph>
        <Descriptions bordered column={1} size="small">
          <Descriptions.Item label="代理端口">8000（HTTP）/ 8443（HTTPS）</Descriptions.Item>
          <Descriptions.Item label="管理端口">8001 / 8444</Descriptions.Item>
          <Descriptions.Item label="后端路由">/api → app-backend:8080</Descriptions.Item>
          <Descriptions.Item label="前端路由">/ → frontend:80</Descriptions.Item>
          <Descriptions.Item label="当前限流">100 请求/分钟（local 策略）</Descriptions.Item>
        </Descriptions>
        <Alert
          message="生产建议"
          description="生产环境可在 Kong 开启 key-auth、openid-connect 或 jwt 插件，统一校验调用方身份，并在网关层统一配置 CORS、限流、日志和监控。"
          type="info"
          showIcon
        />
      </Space>
    ),
  },
  {
    key: 'jwt',
    label: 'JWT 认证',
    icon: <KeyOutlined />,
    content: (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Paragraph>
          后端基于 FastAPI OAuth2 Password Bearer 实现 JWT 认证。外部系统调用 API 时，
          先通过 <Text code>/api/v1/auth/login</Text> 获取 access_token，然后在请求头中携带：
        </Paragraph>
        <pre style={{ background: '#f6ffed', padding: 12, borderRadius: 4 }}>
{`Authorization: Bearer <access_token>`}
        </pre>
        <Descriptions bordered column={1} size="small">
          <Descriptions.Item label="算法">HS256</Descriptions.Item>
          <Descriptions.Item label="Token 有效期">30 分钟（可配置）</Descriptions.Item>
          <Descriptions.Item label="Token 载体">user_id、username、security_level</Descriptions.Item>
        </Descriptions>
      </Space>
    ),
  },
  {
    key: 'apikey',
    label: 'API Key 方案',
    icon: <ApiOutlined />,
    content: (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Paragraph>
          针对服务器间调用，Kong 已预留 key-auth 配置（当前 demo 环境未启用）。启用后，
          每个外部系统分配独立 API Key，在请求头中携带：
        </Paragraph>
        <pre style={{ background: '#fff2e8', padding: 12, borderRadius: 4 }}>
{`api-key: <your-api-key>`}
        </pre>
        <Alert
          message="与 JWT 的互补关系"
          description="API Key 适合系统间无会话调用，JWT 适合用户级有状态调用。两者可在 Kong 分层组合使用。"
          type="warning"
          showIcon
        />
      </Space>
    ),
  },
  {
    key: 'call',
    label: '典型调用示例',
    icon: <CloudServerOutlined />,
    content: (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Paragraph>以下示例展示外部系统如何通过 Kong 调用检索接口：</Paragraph>
        <pre style={{ background: '#f0f2f5', padding: 12, borderRadius: 4, overflow: 'auto' }}>
{`# 1. 登录获取 token
curl -X POST http://localhost:8000/api/v1/auth/login \\
  -d "username=admin&password=admin"

# 2. 调用检索接口
curl -X POST http://localhost:8000/api/v1/search \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "本季度营收情况",
    "kb_ids": ["<kb-id>"],
    "top_k": 5,
    "rerank_top_k": 3
  }'`}
        </pre>
      </Space>
    ),
  },
]

const ProductPage = () => {
  const [activeAuthTab, setActiveAuthTab] = useState('kong')

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Hero */}
      <Card bordered={false} style={{ background: 'linear-gradient(135deg, #1677ff 0%, #0050b3 100%)' }}>
        <Title level={2} style={{ color: '#fff', marginBottom: 12 }}>
          企业级私有化多模态 RAG 平台
        </Title>
        <Paragraph style={{ color: 'rgba(255,255,255,0.9)', fontSize: 16, maxWidth: 800 }}>
          面向金融、制造、政务、能源等行业，提供数据不出域、权限可管控、来源可追溯、多模态可理解的
          企业知识检索与生成平台，让大模型真正安全地服务企业私有知识。
        </Paragraph>
        <Button type="primary" ghost style={{ marginTop: 8, borderColor: '#fff', color: '#fff' }}>
          查看系统文档
        </Button>
      </Card>

      {/* Pain Points */}
      <Card title={<Title level={4} style={{ margin: 0 }}>解决的行业痛点</Title>}>
        <Row gutter={[16, 16]}>
          {painPoints.map((p, idx) => (
            <Col xs={24} md={12} lg={8} key={idx}>
              <Card size="small" hoverable>
                <Space align="start">
                  {p.icon}
                  <div>
                    <Text strong>{p.title}</Text>
                    <Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 4 }}>
                      {p.desc}
                    </Paragraph>
                  </div>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      {/* Permission Structure */}
      <Card title={<Title level={4} style={{ margin: 0 }}>统一权限结构</Title>}>
        <Paragraph>
          系统采用“默认拒绝、五级穿透”的权限模型，从身份到标签逐层过滤，确保检索与生成内容严格受控。
        </Paragraph>
        <Row gutter={[16, 16]}>
          {permissionLayers.map((layer, idx) => (
            <Col xs={24} md={12} lg={8} key={idx}>
              <Card
                size="small"
                title={
                  <Space>
                    <TeamOutlined />
                    <Text strong>{layer.title}</Text>
                  </Space>
                }
              >
                <Space direction="vertical" size={4}>
                  {layer.items.map((item, i) => (
                    <Tag key={i} color="blue" style={{ marginRight: 0 }}>
                      {item}
                    </Tag>
                  ))}
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
        <Divider />
        <Collapse ghost>
          <Panel header="权限校验流程" key="flow">
            <Steps direction="vertical" size="small" current={-1}>
              <Step title="身份认证" description="JWT 解析用户身份与安全等级" />
              <Step title="知识库授权" description="判断用户是否有该知识库访问权限" />
              <Step title="文档 ACL" description="检查文档允许/拒绝列表" />
              <Step title="字段/类型过滤" description="按文件类型和敏感字段配置过滤" />
              <Step title="标签匹配" description="按密级、部门、项目等标签动态过滤" />
              <Step title="结果返回" description="仅返回用户被授权看到的 Chunk" />
            </Steps>
          </Panel>
        </Collapse>
      </Card>

      {/* RAG Architecture */}
      <Card title={<Title level={4} style={{ margin: 0 }}>多模态 RAG 架构</Title>}>
        <Paragraph>
          从多源接入到带引用溯源的生成，形成完整的企业知识处理闭环。
        </Paragraph>
        <Steps direction="horizontal" size="small" current={-1}>
          {ragSteps.map((s, idx) => (
            <Step key={idx} title={s.title} description={s.desc} />
          ))}
        </Steps>
        <Divider />
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Card size="small" title="核心组件">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Web 框架">FastAPI + Python 3.11</Descriptions.Item>
                <Descriptions.Item label="向量数据库">Milvus 2.4</Descriptions.Item>
                <Descriptions.Item label="关系数据库">PostgreSQL 16</Descriptions.Item>
                <Descriptions.Item label="缓存">Redis 7</Descriptions.Item>
                <Descriptions.Item label="消息队列">RabbitMQ 3</Descriptions.Item>
                <Descriptions.Item label="对象存储">MinIO</Descriptions.Item>
                <Descriptions.Item label="网关">Kong 3.5</Descriptions.Item>
                <Descriptions.Item label="前端">React 18 + Vite + Ant Design 5</Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card size="small" title="关键特性">
              <ul style={{ paddingLeft: 18, margin: 0 }}>
                <li>多模态 Chunk 与统一 embedding</li>
                <li>向量 + 关键词 + Rerank 混合检索</li>
                <li>检索结果权限实时过滤</li>
                <li>聊天消息来源可追溯</li>
                <li>流式输出与敏感词拦截</li>
                <li>对话、反馈、协作与评测闭环</li>
                <li>Prometheus + Grafana 可观测</li>
              </ul>
            </Card>
          </Col>
        </Row>
      </Card>

      {/* External Auth & Call */}
      <Card title={<Title level={4} style={{ margin: 0 }}>外部鉴权与调用方案</Title>}>
        <Tabs activeKey={activeAuthTab} onChange={setActiveAuthTab} items={externalAuthTabs.map((t) => ({
          key: t.key,
          label: (
            <Space>
              {t.icon}
              {t.label}
            </Space>
          ),
          children: t.content,
        }))} />
      </Card>
    </Space>
  )
}

export default ProductPage
