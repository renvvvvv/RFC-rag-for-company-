# 06 - 多模态RAG Pipeline设计

> 版本: v1.0 | 日期: 2026-06-10 | 状态: 方案设计阶段

---

## 目录

1. [Pipeline总体架构](#1-pipeline总体架构)
2. [文档RAG Pipeline](#2-文档rag-pipeline)
3. [Excel RAG Pipeline](#3-excel-rag-pipeline)
4. [图片RAG Pipeline](#4-图片rag-pipeline)
5. [视频RAG Pipeline](#5-视频rag-pipeline)
6. [链接RAG Pipeline](#6-链接rag-pipeline)
7. [音频RAG Pipeline【待设计】](#7-音频rag-pipeline待设计)
8. [Pipeline编排与调度](#8-pipeline编排与调度)

---

## 1. Pipeline总体架构

### 1.1 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         统一入口: Ingest Service                              │
│                    (接收文件 → MIME类型识别 → 路由分发)                         │
│         ┌─────────┬─────────┬─────────┬─────────┬─────────┐                  │
│         │ 文档    │ Excel   │ 图片    │ 视频    │ 链接    │ 音频              │
│         │ .pdf    │ .xlsx   │ .jpg    │ .mp4    │ .url    │ .mp3              │
│         │ .docx   │ .csv    │ .png    │ .mov    │         │ .wav              │
│         │ .txt    │         │ .webp   │ .avi    │         │ .m4a              │
│         └────┬────┴────┬────┴────┬────┴────┬────┴────┬────┴────┐             │
└──────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────────┘
               │         │         │         │         │         │
               ▼         ▼         ▼         ▼         ▼         ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ 文档     │ │ Excel    │ │ 图片     │ │ 视频     │ │ 链接     │
        │ Pipeline │ │ Pipeline │ │ Pipeline │ │ Pipeline │ │ Pipeline │
        │ (2)      │ │ (3)      │ │ (4)      │ │ (5)      │ │ (6)      │
        └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │            │            │
             └────────────┴────────────┼────────────┴────────────┘
                                      │
                                      ▼
               ┌──────────────────────────────────────────────────┐
               │              统一向量化层                           │
               │        Embedding Service (用户提供的模型)            │
               │   ┌─────────────┐    ┌─────────────────────────┐  │
               │   │ Dense向量   │    │ Sparse向量 (BM25关键词)  │  │
               │   │ 用户Embedding│   │ 自研Sparse Encoder      │  │
               │   └─────────────┘    └─────────────────────────┘  │
               └──────────────────────┬─────────────────────────────┘
                                      │
                                      ▼
               ┌──────────────────────────────────────────────────┐
               │              统一索引层                             │
               │   ┌─────────────┐    ┌─────────────────────────┐  │
               │   │ 向量数据库   │    │ 关系数据库 (PostgreSQL)  │  │
               │   │ Milvus      │    │ 倒排索引 (Meilisearch)   │  │
               │   └─────────────┘    └─────────────────────────┘  │
               └──────────────────────────────────────────────────┘
```

### 1.2 路由分发逻辑

```
文件上传 / URL提交
    │
    ▼
┌─────────────────────────────────────┐
│ Step 1: MIME类型识别 + 后缀校验      │
│  - 白名单校验: ALLOWED_TYPES        │
│  - magic库读取文件头确认真实类型    │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Step 2: 文件预处理                   │
│  - 病毒扫描 (ClamAV)                │
│  - 大小限制检查                     │
│  - 临时存储到本地磁盘                │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Step 3: 路由分发                     │
│                                      │
│  if ext in ['pdf','docx','doc','txt','md','rst']:
│      → route_to('document_pipeline')
│  elif ext in ['xlsx','xls','csv']:
│      → route_to('excel_pipeline')
│  elif ext in ['jpg','jpeg','png','gif','webp','bmp']:
│      → route_to('image_pipeline')
│  elif ext in ['mp4','avi','mov','mkv','wmv']:
│      → route_to('video_pipeline')
│  elif is_url(input):
│      → route_to('link_pipeline')
│  elif ext in ['mp3','wav','m4a','flac','ogg']:
│      → route_to('audio_pipeline')  # 当前仅存储
│  else:
│      → reject(UnsupportedFileType)
└─────────────────────────────────────┘
```

### 1.3 统一Chunk Schema

所有模态Pipeline最终输出的Chunk必须遵循统一的Schema，确保跨模态检索的一致性：

```python
class Chunk(BaseModel):
    chunk_id: str           # UUID v4
    doc_id: str             # 所属文档ID
    kb_id: str              # 所属知识库ID
    tenant_id: str          # 租户ID
    modality: Literal["document", "excel", "image", "video", "link", "audio"]
    chunk_type: str         # 模态内细分类型 (见各Pipeline定义)
    content: str            # 文本内容 (用于LLM上下文)
    content_html: Optional[str] = None  # 富文本内容 (用于前端展示)
    
    # 向量表示 (至少一种)
    dense_vector: Optional[List[float]] = None      # Dense Embedding
    sparse_vector: Optional[Dict[str, float]] = None # Sparse/BM25
    visual_vector: Optional[List[float]] = None      # 视觉Embedding (图片/视频)
    
    # 权限元数据
    permission_meta: PermissionMeta
    
    # 模态特有元数据
    metadata: Dict[str, Any]
    
    # 溯源信息
    source_info: SourceInfo
    
    # 生命周期
    created_at: datetime
    updated_at: datetime
    status: Literal["active", "deprecated", "pending"]
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chunk_id` | UUID | 是 | 全局唯一标识 |
| `doc_id` | str | 是 | 关联原始文档 |
| `modality` | enum | 是 | 模态分类 |
| `chunk_type` | str | 是 | 模态内类型细分 |
| `content` | str | 是 | 纯文本内容，供LLM使用 |
| `dense_vector` | float[] | 条件 | Dense向量，文档/Excel/链接必填 |
| `sparse_vector` | dict | 条件 | Sparse向量，所有文本类必填 |
| `visual_vector` | float[] | 条件 | 视觉向量，图片/视频必填 |
| `permission_meta` | object | 是 | 权限控制元数据 |
| `metadata` | dict | 是 | 模态特有扩展字段 |
| `source_info` | object | 是 | 溯源信息 (页码/时间戳/URL等) |

---

## 2. 文档RAG Pipeline

### 2.1 Pipeline流程图

```
输入: PDF / Word / TXT / Markdown 文件
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 文档解析 (Document Parsing)                                              │
│    ┌─────────────────┬─────────────────┬─────────────────┐                 │
│    │ PDF             │ Word            │ TXT/MD          │                 │
│    ├─────────────────┼─────────────────┼─────────────────┤                 │
│    │ pdfplumber      │ python-docx     │ 直接读取        │                 │
│    │ unstructured    │ 解析段落+表格   │                 │                 │
│    │ 提取文本+布局   │ +样式+页眉页脚  │                 │                 │
│    └─────────────────┴─────────────────┴─────────────────┘                 │
│    输出: 结构化文档对象 (元素列表 + 位置信息)                                │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. 结构化提取 (Structure Extraction)                                        │
│    - 标题层级识别 (H1-H6): 基于字体大小/样式/缩进                           │
│    - 表格提取: 保留行列关系 + 表头信息                                       │
│    - 列表识别: 有序/无序列表                                                 │
│    - 代码块识别: 等宽字体区域                                                │
│    - 图片引用: 记录图片位置 (图片描述待关联)                                │
│    输出: 带结构标签的元素树                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. 智能分块 (Smart Chunking)                                                │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ 策略选择器: 根据文档类型/长度/结构自动选择最优策略                    │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│                          │                                                  │
│        ┌─────────────────┼─────────────────┐                                │
│        ▼                 ▼                 ▼                                │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                             │
│   │ 策略A    │    │ 策略B    │    │ 策略C    │                             │
│   │ 固定大小 │    │ 语义分块 │    │ 结构感知 │                             │
│   │ 分块     │    │          │    │ 分块     │                             │
│   │          │    │          │    │          │                             │
│   │ chunk_sz │    │ 段落边界 │    │ 表格完整 │                             │
│   │ =512tok  │    │ 章节边界 │    │ 列表完整 │                             │
│   │ overlap  │    │ 语义边界 │    │ 标题关联 │                             │
│   │ =128tok  │    │          │    │          │                             │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘                             │
│        │               │               │                                    │
│        └───────────────┼───────────────┘                                    │
│                        ▼                                                    │
│               ┌────────────────┐                                            │
│               │ 策略D: 混合策略 │                                            │
│               │ 优先语义边界    │                                            │
│               │ 超长强制切割    │                                            │
│               │ 表格不跨chunk   │                                            │
│               └────────────────┘                                            │
│                                                                             │
│    输出: Chunk列表，每个Chunk携带:                                           │
│    - page_range, heading_path, element_types, char_count, token_count       │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. 向量化 (Embedding)                                                       │
│    - Dense向量:  用户提供的Embedding模型 → 文本 → float[]                    │
│    - Sparse向量: 自研Sparse Encoder → BM25关键词权重 → {term: weight}        │
│    输出: (dense_vector, sparse_vector, metadata)                             │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. 索引入库 (Indexing)                                                      │
│    - Dense Vector  → Milvus Collection: `document_dense`                    │
│    - Sparse Vector → Meilisearch 倒排索引                                   │
│    - Metadata      → PostgreSQL chunk表                                     │
│    - 原始文件      → MinIO 对象存储                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 关键设计点

| 设计点 | 方案 | 理由 |
|--------|------|------|
| PDF解析引擎 | `unstructured` + `pdfplumber` 双引擎 | unstructured对复杂版式PDF支持好，pdfplumber对表格提取精度高，双引擎互补 |
| 标题层级识别 | 字体大小排序 + 样式规则 + 位置推断 | 无标签PDF中标题识别是关键，直接影响语义分块质量 |
| 表格处理 | 每个表格生成独立Chunk + 生成文本化描述 | 表格信息密度高，独立索引+文本化描述提升检索召回 |
| 分块策略选择 | 基于文档特征自动选择，支持覆盖 | 技术文档→结构感知，长文小说→语义分块，短通知→固定大小 |
| 双向量索引 | Dense(语义) + Sparse(关键词) 并存 | Dense处理同义改写，Sparse处理专有名词精确匹配 |
| 权限标注 | Chunk级权限标签继承文档级 + 段落级覆盖 | 支持Word段落级权限控制 |

### 2.3 分块策略代码示例

```python
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass

class ChunkStrategy(Enum):
    FIXED_SIZE = "fixed_size"       # 固定大小分块
    SEMANTIC = "semantic"           # 语义分块
    STRUCTURE_AWARE = "structure"   # 结构感知分块
    HYBRID = "hybrid"               # 混合策略（推荐）

@dataclass
class ChunkConfig:
    strategy: ChunkStrategy = ChunkStrategy.HYBRID
    chunk_size: int = 512           # tokens
    chunk_overlap: int = 128        # tokens
    preserve_tables: bool = True    # 表格不跨chunk
    preserve_lists: bool = True     # 列表不跨chunk
    heading_context: bool = True    # chunk携带所属标题路径

def select_chunk_strategy(doc_meta: DocMeta) -> ChunkConfig:
    """根据文档特征自动选择最优分块策略"""
    
    if doc_meta.doc_type == "technical_spec":
        # 技术规格文档: 结构感知，保留章节完整性
        return ChunkConfig(
            strategy=ChunkStrategy.STRUCTURE_AWARE,
            chunk_size=768,
            chunk_overlap=128,
            preserve_tables=True,
            preserve_lists=True,
            heading_context=True
        )
    elif doc_meta.doc_type == "contract":
        # 合同文档: 条款级分块，固定大小为主
        return ChunkConfig(
            strategy=ChunkStrategy.HYBRID,
            chunk_size=384,
            chunk_overlap=64,
            preserve_tables=True,
            heading_context=True
        )
    elif doc_meta.total_tokens < 2048:
        # 短文档: 直接作为一个chunk
        return ChunkConfig(
            strategy=ChunkStrategy.FIXED_SIZE,
            chunk_size=2048,
            chunk_overlap=0
        )
    else:
        # 默认: 混合策略
        return ChunkConfig()

def hybrid_chunking(elements: List[DocElement], config: ChunkConfig) -> List[Chunk]:
    """
    混合分块策略:
    1. 优先按语义边界(标题/段落)分割
    2. 超过chunk_size时强制切割
    3. 表格/列表保持完整
    4. 每个chunk携带标题上下文
    """
    chunks = []
    current_buffer = []
    current_tokens = 0
    heading_path = []  # 当前标题层级路径
    
    for elem in elements:
        # 更新标题路径
        if elem.type == "heading":
            level = elem.level
            heading_path = heading_path[:level-1] + [elem.text]
        
        # 表格和列表作为独立单元处理
        if elem.type in ("table", "list") and config.preserve_tables:
            # 先flush当前buffer
            if current_buffer:
                chunks.append(_create_chunk(current_buffer, heading_path, config))
                current_buffer = []
                current_tokens = 0
            # 表格/列表独立成chunk
            chunks.append(_create_chunk([elem], heading_path, config))
            continue
        
        elem_tokens = elem.token_count
        
        # 检查是否需要切割
        if current_tokens + elem_tokens > config.chunk_size and current_buffer:
            chunks.append(_create_chunk(current_buffer, heading_path, config))
            # 保留overlap
            overlap_elements = _calc_overlap(current_buffer, config.chunk_overlap)
            current_buffer = overlap_elements + [elem]
            current_tokens = sum(e.token_count for e in current_buffer)
        else:
            current_buffer.append(elem)
            current_tokens += elem_tokens
    
    # flush剩余
    if current_buffer:
        chunks.append(_create_chunk(current_buffer, heading_path, config))
    
    return chunks
```

### 2.4 输入/输出/关键设计点汇总

| 维度 | 内容 |
|------|------|
| **输入** | PDF(.pdf), Word(.doc/.docx), 文本(.txt/.md/.rst), 文件流或本地路径 |
| **处理步骤** | ①文档解析 → ②结构化提取 → ③智能分块(4策略) → ④向量化(Dense+Sparse) → ⑤索引入库 |
| **输出** | Chunk列表 (含dense_vector, sparse_vector, 位置元数据, 权限标签) |
| **关键设计点** | 双引擎PDF解析、4种智能分块策略、结构感知语义分块、表格独立Chunk、双向量索引 |

---

## 3. Excel RAG Pipeline

### 3.1 Pipeline流程图

```
输入: Excel文件 (.xlsx/.xls/.csv)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 工作表解析 (Sheet Parsing)                                               │
│    - openpyxl / pandas 读取所有工作表                                        │
│    - 识别合并单元格、表头区域、数据区域                                       │
│    - 提取单元格格式、公式原始表达式、批注                                     │
│    - CSV: 编码自动检测 (chardet) → UTF-8标准化                              │
│                                                                             │
│    输出: [WorkSheet]                                                        │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ WorkSheet: {name, headers[], data[][], merged_cells[], formulas[]}  │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. 结构化提取 (Schema Extraction)                                           │
│    对每个WorkSheet:                                                          │
│    - 列名提取 + 数据类型推断 (str/int/float/date/bool)                       │
│    - 主键候选识别 (唯一值列)                                                 │
│    - 外键关系推断 (列名相似度匹配)                                           │
│    - 生成表级自然语言描述: "工资表包含姓名、部门、薪资等8列"                  │
│    - 统计摘要: 行数、数值列极值、枚举列去重值                                 │
│                                                                             │
│    输出: TableSchema + 清洗后的行数据                                        │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. 多维度分块 (Multi-dimensional Chunking)                                  │
│                                                                             │
│    生成4种Chunk类型:                                                         │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ Type A: 表级描述Chunk (Sheet-level)                                │  │
│    │ 内容: "工资表(Sheet1)包含8列: 姓名、部门、职位... 共156行数据"      │  │
│    │ 用途: 回答"有哪些表"、"某表包含什么字段"等元数据查询              │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ Type B: 列级Chunk (Column-level)                                   │  │
│    │ 内容: "薪资列: 数据类型number, 范围5000-50000, 平均值18000,        │  │
│    │        样本值: [15000, 22000, 18000...]"                            │  │
│    │ 用途: 回答"薪资范围是多少"、"某列统计信息"                        │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ Type C: 行级Chunk (Row-level)                                      │  │
│    │ 内容: "张三, 销售部, 销售经理, 薪资:25000, 入职日期:2022-03-01"    │  │
│    │ 用途: 精确数据查询、实体检索                                        │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ Type D: 区域Chunk (Region-level)                                   │  │
│    │ 内容: 按分组维度聚合 (如按部门分组):                                │  │
│    │       "销售部共15人，薪资范围15000-35000，部门负责人:李四"          │  │
│    │ 用途: 聚合查询、分组统计                                            │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│    输出: 多类型Chunk列表                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. 字段级权限标注 (Field-level Permission Tagging)                          │
│    在每个Chunk的metadata中标注:                                              │
│    - involved_columns: ["姓名", "部门", "薪资"]  ← 涉及列名               │
│    - sheet_name: "Sheet1"                                                   │
│    - row_range: (1, 100) or None                                            │
│    - col_range: ["A", "D"] or None                                         │
│    - permission_level: 继承工作表级 + 列级覆盖                              │
│                                                                             │
│    权限过滤规则:                                                             │
│    - 行级Chunk: 用户必须拥有该行涉及的所有列权限                            │
│    - 列级Chunk: 用户必须拥有该列权限                                        │
│    - 表级Chunk: 仅依赖表级权限                                              │
│    - 区域Chunk: 用户必须拥有该区域涉及的所有列权限                          │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. 向量化与索引入库                                                         │
│    - 表级描述Chunk → Embedding → Milvus Collection `excel_dense`           │
│    - 行级Chunk → Embedding → Milvus Collection `excel_dense`               │
│    - 列级Chunk → Embedding → Milvus Collection `excel_dense`               │
│    - 区域Chunk → Embedding → Milvus Collection `excel_dense`               │
│    - 所有Chunk → Sparse向量 → Meilisearch                                  │
│    - 原始Excel → MinIO存储                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 关键设计点

| 设计点 | 方案 | 理由 |
|--------|------|------|
| 解析引擎 | `openpyxl` + `pandas` | openpyxl保留格式和公式，pandas高效处理大数据量 |
| 表头识别 | 启发式规则: 首行非空 + 数据类型一致性 + 字体加粗 | Excel无显式表头标记，需智能推断 |
| 4种Chunk类型 | 表级/列级/行级/区域 | 覆盖元数据查询、统计查询、精确查询、聚合查询全场景 |
| 行级Chunk生成 | 每行文本化描述 + 批量Embedding (批量API调用) | 控制API调用次数，提升处理效率 |
| 字段级权限 | Chunk.metadata.involved_columns 标注 | 检索时精确过滤，确保越权数据零泄露 |
| 公式处理 | 保留公式文本 + 同时缓存计算值 | 回答"这个单元格怎么算的"时需公式原文 |
| 合并单元格 | 展开填充到所有子单元格 | 保证行级Chunk的每行数据完整性 |

### 3.3 Excel分块代码示例

```python
from typing import List, Dict, Any
import pandas as pd
from dataclasses import dataclass

@dataclass
class ExcelChunk:
    chunk_type: str  # "sheet" | "column" | "row" | "region"
    content: str
    metadata: Dict[str, Any]
    involved_columns: List[str]
    sheet_name: str

def generate_row_chunks(df: pd.DataFrame, sheet_name: str, 
                        columns_meta: Dict) -> List[ExcelChunk]:
    """
    将DataFrame的每一行转换为文本化描述的Chunk。
    批量生成以提高效率。
    """
    chunks = []
    headers = df.columns.tolist()
    
    for idx, row in df.iterrows():
        # 文本化: "列名1:值1, 列名2:值2, ..."
        pairs = [f"{col}:{row[col]}" for col in headers if pd.notna(row[col])]
        content = ", ".join(pairs)
        
        chunk = ExcelChunk(
            chunk_type="row",
            content=content,
            metadata={
                "row_index": idx,
                "sheet_name": sheet_name,
                "row_range": (idx, idx),
            },
            involved_columns=headers,
            sheet_name=sheet_name
        )
        chunks.append(chunk)
    
    return chunks

def generate_region_chunks(df: pd.DataFrame, sheet_name: str,
                           group_by: str) -> List[ExcelChunk]:
    """
    按指定列分组，生成分组聚合描述的Chunk。
    例如按"部门"分组，描述每个部门的统计信息。
    """
    chunks = []
    grouped = df.groupby(group_by)
    
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    for group_name, group_df in grouped:
        stats = []
        for col in numeric_cols:
            stats.append(f"{col}平均{group_df[col].mean():.0f}")
            stats.append(f"{col}范围{group_df[col].min():.0f}-{group_df[col].max():.0f}")
        
        content = (
            f"{group_by}为'{group_name}'的数据共{len(group_df)}行，"
            f"{', '.join(stats[:4])}"
        )
        
        chunk = ExcelChunk(
            chunk_type="region",
            content=content,
            metadata={
                "group_by": group_by,
                "group_value": str(group_name),
                "row_count": len(group_df),
                "row_range": (group_df.index.min(), group_df.index.max()),
            },
            involved_columns=df.columns.tolist(),
            sheet_name=sheet_name
        )
        chunks.append(chunk)
    
    return chunks

def generate_column_chunks(df: pd.DataFrame, sheet_name: str) -> List[ExcelChunk]:
    """为每列生成统计信息Chunk"""
    chunks = []
    
    for col in df.columns:
        col_data = df[col].dropna()
        dtype = str(df[col].dtype)
        
        # 数值型
        if pd.api.types.is_numeric_dtype(df[col]):
            desc = (
                f"{col}列({dtype}): "
                f"共{len(col_data)}个有效值, "
                f"范围{col_data.min():.2f}-{col_data.max():.2f}, "
                f"平均值{col_data.mean():.2f}, "
                f"样本: {', '.join(map(str, col_data.head(5).tolist()))}"
            )
        # 分类型
        elif pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            unique_vals = col_data.unique()[:10]
            desc = (
                f"{col}列(文本): "
                f"共{len(col_data)}个值, "
                f"{len(col_data.unique())}个唯一值, "
                f"样本: {', '.join(map(str, unique_vals))}"
            )
        else:
            desc = f"{col}列({dtype}): 共{len(col_data)}个值"
        
        chunk = ExcelChunk(
            chunk_type="column",
            content=desc,
            metadata={
                "column_name": col,
                "data_type": dtype,
                "unique_count": len(col_data.unique()),
            },
            involved_columns=[col],
            sheet_name=sheet_name
        )
        chunks.append(chunk)
    
    return chunks
```

### 3.4 输入/输出/关键设计点汇总

| 维度 | 内容 |
|------|------|
| **输入** | Excel(.xlsx/.xls), CSV(.csv), 文件流或本地路径 |
| **处理步骤** | ①工作表解析 → ②结构化提取(列名/类型/统计) → ③4种Chunk生成 → ④字段级权限标注 → ⑤向量化+索引 |
| **输出** | 4类Chunk(表级/列级/行级/区域)，每个Chunk携带involved_columns权限元数据 |
| **关键设计点** | 4种Chunk类型覆盖全查询场景、字段级权限involved_columns标注、公式原文保留、合并单元格展开、批量Embedding |

---

## 4. 图片RAG Pipeline

### 4.1 Pipeline流程图

```
输入: 图片文件 (.jpg/.jpeg/.png/.gif/.webp/.bmp)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 图片预处理 (Image Preprocessing)                                         │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ ① 格式标准化                                                        │  │
│    │    - 统一转换为 PNG (无损) 或 WebP (有损压缩)                       │  │
│    │    - 色彩空间: RGB/RGBA                                             │  │
│    │    - 最大边长限制: 4096px (超限缩放)                                │  │
│    ├─────────────────────────────────────────────────────────────────────┤  │
│    │ ② 多尺寸缩略图生成                                                  │  │
│    │    - 64x64:   用于快速预览 + 感知哈希去重                           │  │
│    │    - 256x256: 用于列表展示                                          │  │
│    │    - 512x512: 用于Vision LLM输入 (minimax-m3)                       │  │
│    │    - 原图:    用于高清查看                                          │  │
│    ├─────────────────────────────────────────────────────────────────────┤  │
│    │ ③ 质量检查与去重                                                    │  │
│    │    - 感知哈希 (pHash) 计算 → 全局去重                               │  │
│    │    - 模糊检测 (拉普拉斯方差) → 标记低质量图片                       │  │
│    │    - 文件大小异常检测 → 标记潜在损坏                                │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│    输出: 标准化图片 + 缩略图集合 + 质量标记                                  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. 多维度信息提取 (Multi-dimensional Extraction)                            │
│    并行启动4个处理流:                                                        │
│                                                                             │
│    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  ┌─────────┐  │
│    │ 流A: OCR        │  │ 流B: Vision描述 │  │ 流C: 物体   │  │ 流D:    │  │
│    │     文字识别    │  │     (minimax-m3)│  │     识别    │  │ EXIF    │  │
│    ├─────────────────┤  ├─────────────────┤  ├─────────────┤  ├─────────┤  │
│    │ PaddleOCR       │  │ minimax-m3      │  │ CLIP/       │  │ 拍摄时间│  │
│    │  - 文字区域检测 │  │  - 输入512x512  │  │ 自研分类器  │  │ 拍摄地点│  │
│    │  - 文字内容识别 │  │  - 生成详细描述 │  │  - 场景标签 │  │ 设备型号│  │
│    │  - 位置信息     │  │  - 关键物体列表 │  │  - 物体标签 │  │ GPS坐标 │  │
│    │  - 置信度分数   │  │  - 颜色/风格    │  │  - 置信度   │  │ 方向    │  │
│    └─────────────────┘  └─────────────────┘  └─────────────┘  └─────────┘  │
│                                                                             │
│    输出: StructuredImageInfo                                                │
│    {                                                                        │
│      "ocr_text": "...",           # 识别的全部文字                        │
│      "ocr_regions": [...],        # 文字区域坐标                          │
│      "vision_desc": "...",        # minimax-m3生成的自然语言描述          │
│      "vision_objects": [...],     # 图中关键物体                          │
│      "scene_tags": [...],         # 场景分类标签                          │
│      "object_tags": [...],        # 物体检测标签                          │
│      "exif": {...}                # EXIF元数据                            │
│    }                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. 双向量生成 (Dual Vector Generation)                                      │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ visual_vector (视觉向量)                                           │  │
│    │   来源: minimax-m3 Vision Encoder 提取的图片Embedding              │  │
│    │   用途: "以图搜图"、视觉相似度检索                                  │  │
│    │   维度: 由用户提供的Vision模型决定 (如1024维)                       │  │
│    │   存储: Milvus Collection `image_visual`                           │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ text_vector (文本向量)                                             │  │
│    │   来源: 用户Embedding模型编码 "OCR文本 + Vision描述 + 标签"        │  │
│    │   文本模板:                                                        │  │
│    │   "图片描述: {vision_desc}\n图中文字: {ocr_text}\n标签: {tags}"    │  │
│    │   用途: 文本查询搜图片、语义检索                                    │  │
│    │   维度: 由用户提供的文本Embedding模型决定                           │  │
│    │   存储: Milvus Collection `image_text`                             │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│    同时生成Sparse向量: OCR文本 + 标签 → Sparse Encoder → sparse_vector    │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. 索引入库 (Indexing)                                                      │
│    - visual_vector  → Milvus `image_visual` Collection                      │
│    - text_vector    → Milvus `image_text` Collection                        │
│    - sparse_vector  → Meilisearch                                           │
│    - 原始图片       → MinIO (原图 + 多尺寸缩略图)                            │
│    - 缩略图URL      → 存入metadata，供生成阶段和前端展示引用                  │
│    - 图片URL引用    → 所有关联Chunk的metadata中记录原图URL                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 关键设计点

| 设计点 | 方案 | 理由 |
|--------|------|------|
| OCR引擎 | `PaddleOCR` (中英文优化) | 中文场景识别率优于EasyOCR，支持多语言 |
| Vision描述 | `minimax-m3` Vision能力 | 用户指定模型，生成高质量自然语言描述 |
| 物体/场景识别 | CLIP-based 分类器 | 补充标签信息，提升关键词检索覆盖 |
| 双向量策略 | visual_vector + text_vector | visual_vector用于以图搜图，text_vector用于文本查询搜图 |
| 缩略图策略 | 64/256/512/原图四级 | 不同场景使用不同尺寸，平衡带宽与清晰度 |
| 去重机制 | 感知哈希 (pHash) | 全局检测重复上传，避免冗余索引 |
| OCR区域保留 | 记录文字在图片中的坐标 | 支持前端"点击高亮"和"文字定位"功能 |
| 图片质量门控 | 模糊检测 + 文件完整性检查 | 拒绝不可用的低质量/损坏图片 |

### 4.3 图片Pipeline代码示例

```python
import asyncio
from typing import Tuple, Dict, Any
from dataclasses import dataclass

@dataclass
class ImageVectors:
    visual_vector: List[float]      # 视觉Embedding
    text_vector: List[float]        # 文本Embedding  
    sparse_vector: Dict[str, float] # Sparse向量

class ImageRAGPipeline:
    """图片RAG处理Pipeline"""
    
    def __init__(self, 
                 ocr_engine: OCRInterface,
                 vision_model: VisionInterface,  # minimax-m3
                 embed_model: EmbeddingInterface,
                 sparse_encoder: SparseEncoder):
        self.ocr = ocr_engine
        self.vision = vision_model
        self.embed = embed_model
        self.sparse = sparse_encoder
    
    async def process(self, image_path: str) -> List[Chunk]:
        # Step 1: 预处理
        processed = await self._preprocess(image_path)
        
        # Step 2: 并行多维度提取
        ocr_result, vision_result = await asyncio.gather(
            self._run_ocr(processed.standard_path),
            self._run_vision(processed.thumb_512_path)
        )
        
        # Step 3: 生成双向量
        vectors = await self._generate_vectors(
            processed.standard_path,
            ocr_result,
            vision_result
        )
        
        # Step 4: 构建Chunk
        chunks = self._build_chunks(processed, ocr_result, vision_result, vectors)
        
        return chunks
    
    async def _run_ocr(self, image_path: str) -> OCRResult:
        """PaddleOCR文字识别"""
        result = self.ocr.ocr(image_path, cls=True)
        # 解析结果: [(bbox, text, conf), ...]
        texts = []
        regions = []
        for line in result[0]:
            bbox, text, conf = line
            texts.append(text)
            regions.append({
                "text": text,
                "bbox": bbox,  # 四边形坐标
                "confidence": conf
            })
        return OCRResult(
            full_text="\n".join(texts),
            regions=regions
        )
    
    async def _run_vision(self, image_path: str) -> VisionResult:
        """minimax-m3 Vision描述"""
        prompt = (
            "请详细描述这张图片的内容。包括：\n"
            "1. 图片中主要有什么物体/人物\n"
            "2. 场景/环境描述\n"
            "3. 文字内容（如果有）\n"
            "4. 整体氛围/风格\n"
            "请用自然语言详细描述。"
        )
        response = await self.vision.describe(image_path, prompt)
        return VisionResult(
            description=response.text,
            objects=response.objects,
            colors=response.colors,
            style=response.style
        )
    
    async def _generate_vectors(self, image_path: str,
                                ocr: OCRResult,
                                vision: VisionResult) -> ImageVectors:
        """并行生成双向量"""
        # 构建文本表示
        text_repr = self._build_text_repr(ocr, vision)
        
        visual_vec, text_vec, sparse_vec = await asyncio.gather(
            self.vision.encode_image(image_path),  # 视觉Embedding
            self.embed.encode(text_repr),          # 文本Embedding
            self.sparse.encode(ocr.full_text + " " + vision.description)
        )
        
        return ImageVectors(
            visual_vector=visual_vec,
            text_vector=text_vec,
            sparse_vector=sparse_vec
        )
    
    def _build_text_repr(self, ocr: OCRResult, vision: VisionResult) -> str:
        """构建图片的文本化表示，用于文本Embedding"""
        parts = [
            f"图片描述: {vision.description}",
            f"图中文字: {ocr.full_text}" if ocr.full_text else "",
            f"识别物体: {', '.join(vision.objects)}" if vision.objects else "",
            f"场景标签: {', '.join(vision.tags)}" if vision.tags else "",
        ]
        return "\n".join(filter(None, parts))
    
    def _build_chunks(self, processed, ocr, vision, vectors) -> List[Chunk]:
        """构建图片Chunk"""
        base_meta = {
            "image_url": processed.original_url,
            "thumbnail_urls": {
                "64": processed.thumb_64_url,
                "256": processed.thumb_256_url,
                "512": processed.thumb_512_url,
            },
            "ocr_regions": ocr.regions,
            "vision_objects": vision.objects,
            "image_size": processed.size,
            "mime_type": processed.mime_type,
        }
        
        # 主Chunk: 完整图片信息
        main_chunk = Chunk(
            chunk_id=generate_uuid(),
            chunk_type="image_main",
            content=self._build_text_repr(ocr, vision),
            dense_vector=vectors.text_vector,
            visual_vector=vectors.visual_vector,
            sparse_vector=vectors.sparse_vector,
            metadata=base_meta,
            source_info=SourceInfo(
                page_number=None,
                time_range=None,
                bounding_box=None,
                original_url=processed.original_url
            )
        )
        
        # 可选: 为OCR每个区域生成子Chunk (高密度文档图片)
        region_chunks = []
        if len(ocr.regions) > 10:  # 文档类图片
            for region in ocr.regions:
                region_chunk = Chunk(
                    chunk_type="image_region",
                    content=region["text"],
                    dense_vector=None,  # 不复用，或按需生成
                    sparse_vector=self.sparse.encode(region["text"]),
                    metadata={
                        **base_meta,
                        "region_bbox": region["bbox"],
                        "region_text": region["text"],
                    },
                    source_info=SourceInfo(
                        bounding_box=region["bbox"],
                        original_url=processed.original_url
                    )
                )
                region_chunks.append(region_chunk)
        
        return [main_chunk] + region_chunks
```

### 4.4 图片检索场景

```
场景1: 文本查询搜图片
─────────────────────────────────
用户: "找一下产品发布会的现场照片"
  │
  ▼
文本Embedding("产品发布会的现场照片") 
  │
  ▼
检索 image_text Collection (Dense+Sparse)
  │
  ▼
召回: [图片Chunk-视觉描述含"发布会"、"现场"]
  │
  ▼
返回: 图片URL + 缩略图 + 来源说明


场景2: 以图搜图
─────────────────────────────────
用户: 上传一张产品图片
  │
  ▼
minimax-m3 Vision Encoder → visual_vector
  │
  ▼
检索 image_visual Collection (Dense, visual_vector)
  │
  ▼
召回: 视觉相似图片Chunk
  │
  ▼
返回: 相似产品图片列表


场景3: 图片内容问答
─────────────────────────────────
用户: "这张图表显示了什么趋势？"
  │
  ▼
文本检索召回相关图片Chunk
  │
  ▼
构造Prompt: 
  "问题: 这张图表显示了什么趋势？\n"
  "图片描述: {chunk.content}\n"
  "图片URL: {chunk.metadata.image_url}"
  │
  ▼
调用 minimax-m3 (带图片URL的多模态推理)
  │
  ▼
返回答案 + 引用图片
```

### 4.5 输入/输出/关键设计点汇总

| 维度 | 内容 |
|------|------|
| **输入** | 图片(.jpg/.png/.gif/.webp/.bmp), 文件流或本地路径 |
| **处理步骤** | ①预处理(标准化+缩略图+去重) → ②并行提取(OCR+Vision描述+物体识别+EXIF) → ③双向量生成(visual+text) → ④索引入库 |
| **输出** | 主Chunk(完整图片描述, visual_vector+text_vector+sparse_vector) + 可选区域Chunks |
| **关键设计点** | PaddleOCR中文优化、minimax-m3 Vision描述、双向量策略(visual+text)、四级缩略图、感知哈希去重、OCR区域坐标保留 |

---

## 5. 视频RAG Pipeline

### 5.1 Pipeline流程图

```
输入: 视频文件 (.mp4/.avi/.mov/.mkv/.wmv)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 视频预处理 (Video Preprocessing)                                         │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ ① 格式标准化                                                        │  │
│    │    - FFmpeg统一转码为 MP4(H.264/AAC)                                │  │
│    │    - 统一帧率 (30fps或保持原始)                                     │  │
│    │    - 统一分辨率 (最大1080p，超限缩放)                               │  │
│    ├─────────────────────────────────────────────────────────────────────┤  │
│    │ ② 元数据提取                                                        │  │
│    │    - 时长、分辨率、码率、帧率、编码格式                             │  │
│    │    - 提取首帧作为封面图                                             │  │
│    ├─────────────────────────────────────────────────────────────────────┤  │
│    │ ③ 生成多分辨率预览                                                  │  │
│    │    - 720p: 用于Web端播放                                            │  │
│    │    - 480p: 用于移动端预览                                           │  │
│    │    - 原始视频: 保留用于下载                                         │  │
│    │    > 注: 音频轨道暂不处理（ASR待后续迭代引入）                      │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│    输出: 标准化视频 + 元数据 + 封面图                                        │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. 双流处理 (Dual Stream Processing)                                        │
│    并行启动两个处理流 (当前阶段不含音频):                                    │
│                                                                             │
│    ┌─────────────────────────────────┐    ┌─────────────────────────────┐   │
│    │ 流A: 关键帧提取                  │    │ 流B: 视频分段Vision描述      │   │
│    │ (Keyframe Extraction)           │    │ (Segment Description)       │   │
│    ├─────────────────────────────────┤    ├─────────────────────────────┤   │
│    │                                 │    │                             │   │
│    │ 策略选择 (优先级从高到低):       │    │ 切片策略:                    │   │
│    │                                 │    │ - 固定15秒/片段             │   │
│    │ 1. 场景切换检测 (FFmpeg          │    │   (经测试的最佳长度)         │   │
│    │    scene detection)             │    │ - 边界对齐到关键帧           │   │
│    │    → 检测镜头切换，提取切换帧    │    │   避免描述不完整画面         │   │
│    │                                 │    │                             │   │
│    │ 2. 固定间隔采样                  │    │ 每个片段输入 minimax-m3:    │   │
│    │    → 每5秒提取一帧 (兜底)       │    │ "请详细描述这段视频中       │   │
│    │                                 │    │  发生了什么，包括人物、      │   │
│    │ 输出:                           │    │  动作、场景、物体等"         │   │
│    │ [{time: 0.0s, frame: f_0.jpg}, │    │                             │   │
│    │  {time: 5.2s, frame: f_1.jpg}, │    │ 输出:                       │   │
│    │  {time: 12.8s, frame: f_2.jpg},│    │ [{start: 0s, end: 15s,     │   │
│    │  ...]                           │    │   desc: "..."}, ...]         │   │
│    │                                 │    │                             │   │
│    │ 同时: 对关键帧运行OCR            │    │                             │   │
│    │ 提取画面中出现的文字             │    │                             │   │
│    │                                 │    │                             │   │
│    └─────────────────────────────────┘    └─────────────────────────────┘   │
│                                                                             │
│    > 注: 音频轨道 (extract_audio → ASR → transcript) 待后续迭代引入        │
│    > 当前阶段仅处理视频画面内容                                              │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. 时间对齐与融合 (Temporal Alignment)                                      │
│                                                                             │
│    将流A(关键帧+OCR)和流B(片段描述)按时间轴对齐，生成时间对齐的Chunk:         │
│                                                                             │
│    时间轴: 0s ─────── 15s ─────── 30s ─────── 45s ─────── 60s ──────>      │
│              │           │           │           │           │              │
│    片段B:   [Desc_0-15] [Desc_15-30] [Desc_30-45] [Desc_45-60] ...          │
│              │           │           │           │                           │
│    关键帧A:  ●f@3s       ●f@18s      ●f@33s     ●f@48s    ...              │
│              │           │           │           │                           │
│    OCR:      "会议开始"   "架构图"     "Q3目标"   "总结"                     │
│              │           │           │           │                           │
│    ──────────┴───────────┴───────────┴───────────┴───────────               │
│              │           │           │           │                           │
│    融合Chunk:│           │           │           │                           │
│    ┌─────────┴───────────┐           │           │                           │
│    │ Time: 0s-15s         │           │           │                           │
│    │ - 片段描述: Desc_0-15│           │           │                           │
│    │ - 关键帧: [f@3s]      │           │           │                           │
│    │ - OCR: "会议开始"     │           │           │                           │
│    └─────────────────────┘           │           │                           │
│                                        │           │                           │
│                            ┌───────────┴───────────┐                         │
│                            │ Time: 15s-30s         │                         │
│                            │ - 片段描述: Desc_15-30│                         │
│                            │ - 关键帧: [f@18s]      │                         │
│                            │ - OCR: "架构图"       │                         │
│                            └───────────────────────┘                         │
│                                                                             │
│    输出: 时间对齐的VisualChunk列表，每个Chunk携带时间戳范围                   │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. 多模态向量化 (Multimodal Embedding)                                      │
│                                                                             │
│    每个时间段Chunk生成多向量表示:                                            │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ text_vector (文本向量)                                             │  │
│    │   文本 = "{片段描述} {OCR文本} {时间戳}"                           │  │
│    │   → 用户Embedding模型 → float[]                                    │  │
│    │   → Milvus Collection `video_text`                                 │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ visual_vector (视觉向量)                                           │  │
│    │   输入 = 关键帧图片 (或关键帧集合的平均)                            │  │
│    │   → minimax-m3 Vision Encoder → float[]                            │  │
│    │   → Milvus Collection `video_visual`                               │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ sparse_vector (稀疏向量)                                           │  │
│    │   输入 = 片段描述 + OCR文本                                         │  │
│    │   → Sparse Encoder → {term: weight}                                │  │
│    │   → Meilisearch                                                    │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. 索引入库 (Indexing)                                                      │
│    - text_vector   → Milvus `video_text` Collection                         │
│    - visual_vector → Milvus `video_visual` Collection                       │
│    - sparse_vector → Meilisearch                                            │
│    - 关键帧图片    → MinIO (按时间戳命名: frame_{doc_id}_{timestamp}.jpg)   │
│    - 标准化视频    → MinIO                                                  │
│    - 所有Chunk关联到同一doc_id，支持按doc_id聚合                            │
│    - 时间戳URL: video_url#t={start_seconds} → 支持直接跳转到片段            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 关键设计点

| 设计点 | 方案 | 理由 |
|--------|------|------|
| 视频转码 | FFmpeg统一转MP4(H.264) | 确保前端播放器兼容性，统一处理流程 |
| 关键帧提取 | 场景切换检测优先 + 固定间隔兜底 | 场景切换帧信息密度最高，减少冗余 |
| 切片长度 | 15秒/片段 | 平衡描述完整性与处理开销，经测试效果最佳 |
| Vision描述 | minimax-m3 对每15秒片段生成描述 | 利用用户指定Vision模型，生成高质量语义描述 |
| 时间对齐 | 关键帧+描述按时间轴融合 | 支持精确时间定位，回答"第X分钟发生了什么" |
| 关键帧OCR | 对每帧运行PaddleOCR | 提取画面文字（如PPT演示、字幕等） |
| 多向量索引 | text_vector + visual_vector + sparse_vector | 文本查询→text向量，以图搜视频→visual向量，关键词→sparse |
| 音频处理 | 🚧 当前不处理，仅提取音频轨道存储 | ASR Pipeline待后续迭代 |
| 视频跳转 | 存储时间戳URL (video.mp4#t=330) | 检索结果支持直接跳转到对应片段 |

### 5.3 视频Pipeline代码示例

```python
import subprocess
import asyncio
from typing import List, Tuple
from dataclasses import dataclass
from pathlib import Path

@dataclass
class VideoSegment:
    start_sec: float
    end_sec: float
    keyframes: List[str]       # 关键帧文件路径列表
    description: str = ""      # minimax-m3描述
    ocr_text: str = ""         # 关键帧OCR文本

class VideoRAGPipeline:
    """视频RAG处理Pipeline (当前不含ASR)"""
    
    SEGMENT_DURATION = 15  # 15秒/片段
    
    def __init__(self,
                 vision_model: VisionInterface,   # minimax-m3
                 ocr_engine: OCRInterface,        # PaddleOCR
                 embed_model: EmbeddingInterface,
                 sparse_encoder: SparseEncoder):
        self.vision = vision_model
        self.ocr = ocr_engine
        self.embed = embed_model
        self.sparse = sparse_encoder
    
    async def process(self, video_path: str, doc_id: str) -> List[Chunk]:
        """主处理流程"""
        # Step 1: 预处理
        meta = await self._preprocess(video_path, doc_id)
        
        # Step 2: 并行双流处理
        segments = await self._dual_stream_process(meta, doc_id)
        
        # Step 3: 向量化
        chunks = await self._vectorize_segments(segments, meta, doc_id)
        
        return chunks
    
    async def _preprocess(self, video_path: str, doc_id: str) -> VideoMeta:
        """FFmpeg标准化转码 + 元数据提取"""
        output_path = f"/tmp/processed/{doc_id}.mp4"
        
        # 标准化转码
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-vf", "scale='min(1920,iw)':-2",  # 最大宽度1920，保持比例
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # 提取元数据
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "json", output_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = json.loads(probe_result.stdout)["format"]["duration"]
        
        # 提取封面图 (首帧)
        cover_path = f"/tmp/processed/{doc_id}_cover.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-i", output_path,
            "-ss", "00:00:00", "-vframes", "1",
            cover_path
        ], check=True, capture_output=True)
        
        return VideoMeta(
            path=output_path,
            duration=float(duration),
            cover_path=cover_path
        )
    
    async def _dual_stream_process(self, meta: VideoMeta, doc_id: str) -> List[VideoSegment]:
        """双流并行处理"""
        # 流A: 关键帧提取
        keyframes = await self._extract_keyframes(meta, doc_id)
        
        # 流B: 分段Vision描述
        descriptions = await self._describe_segments(meta, doc_id)
        
        # 时间对齐与融合
        segments = self._align_streams(keyframes, descriptions, meta.duration)
        
        # 对关键帧OCR (可在对齐后批量执行)
        for seg in segments:
            seg.ocr_text = await self._ocr_keyframes(seg.keyframes)
        
        return segments
    
    async def _extract_keyframes(self, meta: VideoMeta, doc_id: str) -> List[Tuple[float, str]]:
        """
        关键帧提取: 先尝试场景切换检测，无结果则固定间隔采样
        """
        output_dir = f"/tmp/keyframes/{doc_id}"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 方案1: 场景切换检测
        scene_cmd = [
            "ffmpeg", "-i", meta.path,
            "-vf", "select='gt(scene,0.3)',showinfo",
            "-vsync", "vfr",
            f"{output_dir}/scene_%04d.jpg"
        ]
        result = subprocess.run(scene_cmd, capture_output=True)
        
        scene_files = sorted(Path(output_dir).glob("scene_*.jpg"))
        
        if len(scene_files) >= 3:
            # 场景检测成功，解析时间戳 (从stderr提取)
            keyframes = self._parse_scene_timestamps(result.stderr.decode(), scene_files)
        else:
            # 方案2: 固定间隔采样 (每5秒一帧)
            keyframes = await self._fixed_interval_sampling(meta, doc_id, interval=5)
        
        return keyframes
    
    async def _describe_segments(self, meta: VideoMeta, doc_id: str) -> List[Tuple[float, str]]:
        """
        将视频切分为15秒片段，用minimax-m3生成描述
        """
        segments = []
        num_segments = int(meta.duration // self.SEGMENT_DURATION) + 1
        
        for i in range(num_segments):
            start = i * self.SEGMENT_DURATION
            end = min((i + 1) * self.SEGMENT_DURATION, meta.duration)
            
            # 提取片段中间帧作为Vision输入
            mid = (start + end) / 2
            frame_path = f"/tmp/segments/{doc_id}_seg{i}_mid.jpg"
            Path("/tmp/segments").mkdir(parents=True, exist_ok=True)
            
            subprocess.run([
                "ffmpeg", "-y", "-i", meta.path,
                "-ss", str(mid), "-vframes", "1",
                frame_path
            ], check=True, capture_output=True)
            
            # minimax-m3 Vision描述
            prompt = (
                "请详细描述这段视频中发生的事情。包括：\n"
                "1. 场景和环境\n"
                "2. 出现的人物及其动作\n" 
                "3. 画面中的物体、文字、图表\n"
                "4. 整体活动和事件\n"
                "请用自然语言详细描述。"
            )
            desc = await self.vision.describe(frame_path, prompt)
            segments.append((start, desc.text))
        
        return segments
    
    def _align_streams(self, keyframes: List[Tuple[float, str]], 
                       descriptions: List[Tuple[float, str]],
                       duration: float) -> List[VideoSegment]:
        """
        将关键帧和描述按时间轴对齐。
        每个15秒时间段内归属对应的关键帧和描述。
        """
        segments = []
        num_segments = int(duration // self.SEGMENT_DURATION) + 1
        
        for i in range(num_segments):
            seg_start = i * self.SEGMENT_DURATION
            seg_end = min((i + 1) * self.SEGMENT_DURATION, duration)
            
            # 归属该时间段的关键帧
            seg_keyframes = [
                path for ts, path in keyframes 
                if seg_start <= ts < seg_end
            ]
            
            # 该时间段的描述
            seg_desc = descriptions[i][1] if i < len(descriptions) else ""
            
            segments.append(VideoSegment(
                start_sec=seg_start,
                end_sec=seg_end,
                keyframes=seg_keyframes,
                description=seg_desc
            ))
        
        return segments
    
    async def _vectorize_segments(self, segments: List[VideoSegment],
                                  meta: VideoMeta, doc_id: str) -> List[Chunk]:
        """为每个Segment生成多向量并构建Chunk"""
        chunks = []
        
        for seg in segments:
            # 构建文本表示
            text_repr = f"视频片段({seg.start_sec:.0f}s-{seg.end_sec:.0f}s): {seg.description}"
            if seg.ocr_text:
                text_repr += f"\n画面文字: {seg.ocr_text}"
            
            # 并行生成向量
            text_vec, sparse_vec = await asyncio.gather(
                self.embed.encode(text_repr),
                self.sparse.encode(text_repr)
            )
            
            # visual_vector: 取第一个关键帧 (或平均)
            visual_vec = None
            if seg.keyframes:
                visual_vec = await self.vision.encode_image(seg.keyframes[0])
            
            chunk = Chunk(
                chunk_type="video_segment",
                content=text_repr,
                dense_vector=text_vec,
                visual_vector=visual_vec,
                sparse_vector=sparse_vec,
                metadata={
                    "time_start": seg.start_sec,
                    "time_end": seg.end_sec,
                    "duration": seg.end_sec - seg.start_sec,
                    "keyframes": seg.keyframes,
                    "has_ocr": bool(seg.ocr_text),
                },
                source_info=SourceInfo(
                    time_range=(seg.start_sec, seg.end_sec),
                    original_url=f"{VIDEO_BASE_URL}/{doc_id}.mp4#t={int(seg.start_sec)}"
                )
            )
            chunks.append(chunk)
        
        return chunks
```

### 5.4 视频检索结果示例

```json
{
  "chunk_id": "vid-uuid-001",
  "doc_id": "product_planning_Q3.mp4",
  "modality": "video",
  "chunk_type": "video_segment",
  "content": "视频片段(330s-345s): CEO张三正在白板前讲解产品架构图，白板上画着三层架构图，底层是数据层，中间是服务层，上层是应用层。会议室中有约20人在听。\n画面文字: Q3目标 销售额 增长30%",
  "dense_vector": [0.12, -0.05, ...],
  "visual_vector": [0.34, 0.01, ...],
  "sparse_vector": {"CEO": 0.8, "架构图": 0.9, "Q3": 0.7},
  "metadata": {
    "time_start": 330,
    "time_end": 345,
    "duration": 15,
    "keyframes": [
      "/tmp/keyframes/doc001/scene_0234.jpg",
      "/tmp/keyframes/doc001/scene_0235.jpg"
    ],
    "has_ocr": true
  },
  "source_info": {
    "time_range": [330, 345],
    "original_url": "https://minio.example.com/videos/doc001.mp4#t=330"
  }
}
```

### 5.5 输入/输出/关键设计点汇总

| 维度 | 内容 |
|------|------|
| **输入** | 视频(.mp4/.avi/.mov/.mkv/.wmv), 文件流或本地路径 |
| **处理步骤** | ①预处理(FFmpeg标准化+元数据) → ②双流处理(关键帧提取 + 15秒片段Vision描述) → ③时间对齐融合 → ④多向量生成(text+visual+sparse) → ⑤索引入库 |
| **输出** | 时间对齐的VideoSegment Chunk列表，每个含时间戳、关键帧、视觉描述、OCR文本、多向量 |
| **关键设计点** | 场景切换检测优先的关键帧提取、15秒最优切片、minimax-m3 Vision描述、关键帧OCR、时间对齐融合、视频URL时间戳跳转(#t=)、🚧不含ASR |

---

## 6. 链接RAG Pipeline

### 6.1 Pipeline流程图

```
输入: URL链接 (http/https)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 网页抓取 (Web Scraping)                                                  │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ 引擎: Playwright (Chromium headless)                                │  │
│    ├─────────────────────────────────────────────────────────────────────┤  │
│    │ 配置策略:                                                           │  │
│    │ - User-Agent轮换: 模拟真实浏览器                                     │  │
│    │ - Cookie处理: 支持预设Cookie/自动登录                                │  │
│    │ - 请求超时: 30s                                                     │  │
│    │ - 页面加载等待: wait_until="networkidle"                            │  │
│    │ - JS渲染: 完整渲染SPA页面                                           │  │
│    │ - 重试策略: 3次重试，指数退避                                       │  │
│    ├─────────────────────────────────────────────────────────────────────┤  │
│    │ 反爬应对:                                                           │  │
│    │ - 请求频率限制 (每域名1req/2s)                                       │  │
│    │ - 随机延迟 (1-3s)                                                   │  │
│    │ - robots.txt 尊重 (可配置跳过)                                      │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│    输出: 原始HTML + 页面截图 (用于质量校验)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. 正文提取 (Content Extraction)                                            │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ 策略选择 (按优先级):                                                 │  │
│    │                                                                    │  │
│    │ 1. 结构化数据提取 (JSON-LD / Microdata / Open Graph)               │  │
│    │    - 提取标题、作者、发布时间、摘要                                  │  │
│    │                                                                    │  │
│    │ 2. HTML语义标签提取                                                │  │
│    │    - article / main / section 标签优先                              │  │
│    │    - 排除 nav / aside / footer / header / sidebar                   │  │
│    │                                                                    │  │
│    │ 3. 密度算法兜底 (基于文本密度)                                      │  │
│    │    - 计算各节点的 文本长度/标签数 比值                               │  │
│    │    - 选择密度最高的连续区域作为正文                                  │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│    提取内容:                                                                 │
│    - 标题 (title / h1 / og:title)                                         │
│    - 作者/来源 (author / og:site_name)                                    │
│    - 发布时间 (published_time / article:published_time)                    │
│    - 正文段落 (按<p>标签分段，保留原始顺序)                                 │
│    - 内嵌表格 (保留HTML结构，后续文本化)                                    │
│    - 内嵌图片 (下载并走图片Pipeline，可选)                                  │
│    - 内嵌链接 (记录锚文本和URL)                                            │
│                                                                             │
│    清洗规则:                                                                 │
│    - 移除广告区块 (常见class/id关键词匹配)                                  │
│    - 移除导航/面包屑                                                        │
│    - 移除社交分享按钮                                                       │
│    - 统一空白字符                                                           │
│                                                                             │
│    输出: 结构化网页内容 (StructuredWebContent)                              │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. 虚拟文档处理 (Virtual Document Processing)                               │
│                                                                             │
│    将提取的正文内容视为"虚拟文档"，复用文档Pipeline处理:                      │
│                                                                             │
│    网页正文内容                                                              │
│         │                                                                   │
│         ▼                                                                   │
│    ┌─────────────────────────────┐                                          │
│    │ 转换为 Document对象          │                                          │
│    │  - 标题 → H1                 │                                          │
│    │  - 段落 → <p>               │                                          │
│    │  - 表格 → <table>           │                                          │
│    └─────────────────────────────┘                                          │
│         │                                                                   │
│         ▼                                                                   │
│    ┌─────────────────────────────┐                                          │
│    │ 复用文档Pipeline:            │                                          │
│    │  结构化提取 → 智能分块       │                                          │
│    │  → 向量化 → 索引入库         │                                          │
│    └─────────────────────────────┘                                          │
│                                                                             │
│    特殊处理:                                                                 │
│    - metadata中强制注入原始URL                                               │
│    - metadata中注入抓取时间                                                  │
│    - metadata中注入标题和作者                                                │
│    - 生成答案时必须引用原始URL (非本地存储路径)                               │
│    - 支持配置"过期时间"，过期后自动重新抓取                                   │
│    - 支持配置"抓取深度"，处理列表页→详情页                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 关键设计点

| 设计点 | 方案 | 理由 |
|--------|------|------|
| 抓取引擎 | `Playwright` (Chromium headless) | 支持JS渲染，SPA页面也能完整抓取 |
| 正文提取 | 结构化数据 → 语义标签 → 密度算法 (三级降级) | 最大化提取成功率，复杂页面也能提取 |
| 反爬策略 | User-Agent轮换 + 频率限制 + 随机延迟 | 降低被封禁概率，尊重目标网站 |
| 复用文档Pipeline | 提取正文后走文档Pipeline | 避免重复实现分块/向量化逻辑，保持一致性 |
| URL溯源 | metadata强制注入原始URL，答案引用原链接 | 用户可追溯原始信息源，满足合规要求 |
| 过期刷新 | 支持配置ttl (默认30天)，过期自动重新抓取 | 网页内容可能更新，确保检索时效性 |
| 链接去重 | 基于URL规范化 + 内容哈希 | 避免同一页面多次索引 |
| 失败降级 | 抓取失败时保留上次成功内容 (如果有) | 确保服务可用性，不因目标网站故障影响已有内容 |

### 6.3 链接Pipeline代码示例

```python
import hashlib
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright
from typing import Optional

class LinkRAGPipeline:
    """链接RAG处理Pipeline"""
    
    def __init__(self, 
                 doc_pipeline: DocumentRAGPipeline,
                 image_pipeline: Optional[ImageRAGPipeline] = None):
        self.doc_pipeline = doc_pipeline
        self.image_pipeline = image_pipeline
        self.seen_urls = set()  # URL去重集合
    
    async def process(self, url: str, config: LinkConfig = None) -> List[Chunk]:
        """主处理流程"""
        config = config or LinkConfig()
        
        # Step 1: 抓取
        raw_html = await self._scrape(url, config)
        if not raw_html:
            raise ScrapingError(f"Failed to scrape {url}")
        
        # Step 2: 正文提取
        content = self._extract_content(raw_html, url)
        
        # Step 3: 转换为虚拟文档
        virtual_doc = self._build_virtual_document(content, url)
        
        # Step 4: 复用文档Pipeline
        chunks = await self.doc_pipeline.process_virtual(virtual_doc)
        
        # Step 5: 注入链接特有metadata
        for chunk in chunks:
            chunk.metadata["source_url"] = url
            chunk.metadata["source_title"] = content.title
            chunk.metadata["source_author"] = content.author
            chunk.metadata["source_published"] = content.published_time
            chunk.metadata["scraped_at"] = datetime.utcnow().isoformat()
            chunk.metadata["url_hash"] = hashlib.sha256(url.encode()).hexdigest()[:16]
            chunk.source_info.original_url = url
        
        return chunks
    
    async def _scrape(self, url: str, config: LinkConfig) -> Optional[str]:
        """Playwright抓取网页"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=config.user_agent or self._rotate_ua(),
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                # 额外等待JS渲染
                await page.wait_for_timeout(2000)
                html = await page.content()
                return html
            except Exception as e:
                logger.warning(f"Scraping failed for {url}: {e}")
                return None
            finally:
                await browser.close()
    
    def _extract_content(self, html: str, url: str) -> WebContent:
        """
        三级正文提取策略
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        
        # Level 1: 结构化数据
        title = self._extract_meta(soup, ["og:title", "twitter:title"]) or soup.title.string or ""
        author = self._extract_meta(soup, ["author", "og:site_name"])
        published = self._extract_meta(soup, ["article:published_time", "published_time"])
        
        # Level 2: 语义标签提取
        article = soup.find('article') or soup.find('main')
        if article:
            body_html = str(article)
        else:
            # Level 3: 密度算法兜底
            body_html = self._density_extraction(soup)
        
        # 清洗
        body_text = self._clean_body(body_html)
        
        return WebContent(
            title=title.strip(),
            author=author,
            published_time=published,
            body_text=body_text,
            body_html=body_html,
            url=url
        )
    
    def _density_extraction(self, soup: BeautifulSoup) -> str:
        """
        基于文本密度的正文提取算法 (简化版)
        """
        candidates = []
        for elem in soup.find_all(['div', 'section', 'td']):
            text_len = len(elem.get_text(strip=True))
            tag_count = len(elem.find_all())
            if tag_count == 0:
                continue
            density = text_len / tag_count
            candidates.append((density, elem))
        
        # 取密度最高的连续区域
        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates:
            return str(candidates[0][1])
        return ""
    
    def _build_virtual_document(self, content: WebContent, url: str) -> VirtualDocument:
        """将网页内容转换为虚拟Document对象"""
        # 构建伪HTML结构
        html_parts = [
            f"<h1>{content.title}</h1>",
            f"<p>来源: {content.author or '未知'}</p>" if content.author else "",
            f"<p>发布时间: {content.published_time}</p>" if content.published_time else "",
            "<hr/>",
        ]
        
        # 将正文按段落分割
        paragraphs = [p.strip() for p in content.body_text.split('\n') if p.strip()]
        for p in paragraphs:
            html_parts.append(f"<p>{p}</p>")
        
        virtual_html = "\n".join(filter(None, html_parts))
        
        return VirtualDocument(
            doc_id=f"link_{hashlib.sha256(url.encode()).hexdigest()[:16]}",
            html=virtual_html,
            text=content.body_text,
            title=content.title,
            source_url=url
        )
```

### 6.4 输入/输出/关键设计点汇总

| 维度 | 内容 |
|------|------|
| **输入** | HTTP/HTTPS URL |
| **处理步骤** | ①Playwright抓取(JS渲染) → ②三级正文提取(结构化→语义标签→密度算法) → ③转换为虚拟文档 → ④复用文档Pipeline(分块→向量化→索引) |
| **输出** | 复用文档Chunk格式，metadata强制注入source_url/source_title/source_author/scraped_at |
| **关键设计点** | Playwright支持SPA、三级正文提取降级、反爬策略(UA轮换+频率限制)、复用文档Pipeline避免重复实现、URL溯源强制注入、支持ttl过期刷新 |

---

## 7. 音频RAG Pipeline【待设计】

### 7.1 当前阶段处理

```
输入: 音频文件 (.mp3/.wav/.m4a/.flac/.ogg)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           当前阶段处理流程                                   │
│                                                                             │
│   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     │
│   │ 文件上传        │ --> │ MinIO对象存储   │ --> │ 状态标记        │     │
│   │                 │     │                 │     │ stored_only     │     │
│   └─────────────────┘     └─────────────────┘     └─────────────────┘     │
│                                                                             │
│   - 仅提供文件下载/播放，不参与RAG检索                                       │
│   - 前端展示: 音频播放器 + 文件名 + 时长(FFmpeg提取)                         │
│   - 不参与任何向量索引和语义检索                                             │
│                                                                             │
│   状态机:                                                                    │
│   ┌──────────┐    ┌─────────────┐    ┌──────────┐                         │
│   │ uploaded │ --> │ processing  │ --> │ stored   │                         │
│   └──────────┘    └─────────────┘    └──────────┘                         │
│        │               (提取元数据)    (stored_only)                       │
│        └──────────────────────────────────────────────────────────────>     │
│                    上传失败 → failed                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 预留完整Pipeline设计（后续迭代）

```
输入: 音频文件 (.mp3/.wav/.m4a/.flac/.ogg)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 音频预处理 (Audio Preprocessing)                                         │
│    - 格式标准化: 统一转为 WAV (16kHz, 16bit, 单声道)                        │
│    - 音频质量检查: 信噪比检测、静音段检测                                     │
│    - 分通道处理 (如立体声 → 单声道合并)                                      │
│    输出: 标准化音频 + 质量标记                                               │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. 语音转文字 (ASR - Automatic Speech Recognition)                          │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ ASR引擎选择 (待选型):                                               │  │
│    │ - 方案A: Whisper / Whisper-large-v3 (OpenAI)                        │  │
│    │   优点: 多语言支持好，开源可私有化部署                              │  │
│    │   缺点: 中文专有名词识别有提升空间                                  │  │
│    │                                                                     │  │
│    │ - 方案B: 讯飞/百度/阿里 企业级ASR API                               │  │
│    │   优点: 中文识别率高，支持领域定制                                  │  │
│    │   缺点: 非私有化，需评估数据安全                                    │  │
│    │                                                                     │  │
│    │ - 方案C: 自研ASR (基于Wav2Vec2/BERT-like)                          │  │
│    │   优点: 完全私有化，可领域微调                                      │  │
│    │   缺点: 投入大，维护成本高                                          │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│    输出要求:                                                                 │
│    - 完整转录文本                                                            │
│    - 时间戳对齐 (word-level或sentence-level)                                 │
│    - 置信度分数                                                              │
│    - 说话人标识 (如启用Diarization)                                         │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. 说话人分离 (Diarization) 【可选，高优先级】                               │
│    - 区分不同说话人 (Speaker A, Speaker B, ...)                             │
│    - 输出: [{speaker: "A", start: 0.5, end: 3.2, text: "..."}, ...]         │
│    - 应用场景: 会议纪要、访谈记录、多人会议                                   │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. 语义分块 (Semantic Chunking)                                             │
│    不同于固定时长分块，基于语义边界分割:                                      │
│    - 句子/段落边界                                                            │
│    - 话题切换检测 (基于语义相似度突变)                                        │
│    - 说话人切换 (如启用Diarization)                                          │
│    - 静音段 (自然停顿点)                                                     │
│                                                                             │
│    每个Chunk携带:                                                            │
│    - time_range: (start_sec, end_sec)                                       │
│    - speaker: "A" (如可用)                                                  │
│    - text: 转录文本                                                          │
│    - confidence: 平均置信度                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. 向量化与索引入库                                                         │
│    - Dense向量: Embedding(转录文本) → Milvus `audio_dense`                 │
│    - Sparse向量: Sparse Encoder(转录文本) → Meilisearch                     │
│    - 原始音频: MinIO存储                                                     │
│    - 时间戳URL: audio.mp3#t={start_sec} 支持跳转到对应片段                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 关键设计点

| 设计点 | 当前方案 | 后续迭代方案 |
|--------|----------|-------------|
| 处理状态 | stored_only，仅存储 | 完整Pipeline: ASR → Diarization → 语义分块 → 向量化 |
| ASR引擎 | 不涉及 | 待选型 (Whisper / 企业API / 自研) |
| 分块策略 | 不涉及 | 语义边界 + 说话人切换 + 话题切换 |
| 时间戳 | FFmpeg提取总时长 | ASR输出的sentence-level时间戳 |
| 说话人分离 | 不涉及 | pyannote-audio / 自研Diarization |
| 向量索引 | 不入索引 | Dense + Sparse 双索引 |
| 音频跳转 | 不支持 | audio.mp4#t= 时间戳跳转 |

### 7.4 输入/输出/关键设计点汇总

| 维度 | 内容 |
|------|------|
| **输入** | 音频(.mp3/.wav/.m4a/.flac/.ogg), 文件流或本地路径 |
| **当前处理** | 仅存储到MinIO，状态标记`stored_only`，不入任何检索索引，前端提供播放功能 |
| **预留Pipeline** | ①预处理(标准化) → ②ASR语音转文字 → ③说话人分离(Diarization) → ④语义分块 → ⑤向量化(Dense+Sparse) → ⑥索引入库 |
| **关键设计点** | 当前仅存储不参与检索、ASR引擎待选型(Whisper/企业API/自研)、预留说话人分离、语义分块基于话题切换检测 |

---

## 8. Pipeline编排与调度

### 8.1 Celery工作流定义

使用 **Celery + 自定义DAG** 实现Pipeline的可编排执行:

```python
# pipelines/config.py

from celery import chain, group, chord
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    TIMEOUT = "timeout"

@dataclass
class PipelineStep:
    """Pipeline步骤定义"""
    name: str                       # 步骤名称
    task: str                       # Celery任务路径 (如 "tasks.document.parse")
    depends_on: List[str] = None    # 依赖的前置步骤
    timeout: int = 300              # 超时时间(秒)
    max_retries: int = 3            # 最大重试次数
    retry_delay: int = 10           # 重试延迟(秒)
    retry_backoff: bool = True      # 指数退避
    retry_backoff_max: int = 600    # 最大退避时间
    on_failure: str = "fail_pipeline"  # 失败处理: fail_pipeline / skip / fallback
    fallback_task: Optional[str] = None  # 降级任务


# ═══════════════════════════════════════════════════════════════
# 各模态Pipeline定义
# ═══════════════════════════════════════════════════════════════

DOCUMENT_PIPELINE = {
    "name": "document_ingest",
    "description": "文档RAG处理Pipeline (PDF/Word/TXT)",
    "steps": [
        PipelineStep(
            name="parse",
            task="pipelines.document.parse",
            timeout=120,
            max_retries=2,
        ),
        PipelineStep(
            name="extract_structure",
            task="pipelines.document.extract_structure",
            depends_on=["parse"],
            timeout=60,
            max_retries=2,
        ),
        PipelineStep(
            name="chunk",
            task="pipelines.document.chunk",
            depends_on=["extract_structure"],
            timeout=60,
            max_retries=2,
        ),
        PipelineStep(
            name="embed",
            task="pipelines.common.embed",
            depends_on=["chunk"],
            timeout=180,
            max_retries=3,
            retry_backoff=True,
        ),
        PipelineStep(
            name="index",
            task="pipelines.common.index",
            depends_on=["embed"],
            timeout=120,
            max_retries=3,
        ),
    ]
}

EXCEL_PIPELINE = {
    "name": "excel_ingest",
    "description": "Excel RAG处理Pipeline",
    "steps": [
        PipelineStep(
            name="parse_sheets",
            task="pipelines.excel.parse_sheets",
            timeout=120,
        ),
        PipelineStep(
            name="extract_schema",
            task="pipelines.excel.extract_schema",
            depends_on=["parse_sheets"],
            timeout=60,
        ),
        PipelineStep(
            name="generate_chunks",
            task="pipelines.excel.generate_chunks",
            depends_on=["extract_schema"],
            timeout=120,
        ),
        PipelineStep(
            name="annotate_permissions",
            task="pipelines.excel.annotate_permissions",
            depends_on=["generate_chunks"],
            timeout=60,
        ),
        PipelineStep(
            name="embed",
            task="pipelines.common.embed",
            depends_on=["annotate_permissions"],
            timeout=180,
            max_retries=3,
        ),
        PipelineStep(
            name="index",
            task="pipelines.common.index",
            depends_on=["embed"],
            timeout=120,
            max_retries=3,
        ),
    ]
}

IMAGE_PIPELINE = {
    "name": "image_ingest",
    "description": "图片RAG处理Pipeline",
    "steps": [
        PipelineStep(
            name="preprocess",
            task="pipelines.image.preprocess",
            timeout=60,
        ),
        PipelineStep(
            name="extract_multimodal",
            task="pipelines.image.extract_multimodal",
            depends_on=["preprocess"],
            timeout=180,
            max_retries=2,
            on_failure="skip",  # OCR失败可跳过，仅用Vision描述
        ),
        PipelineStep(
            name="generate_vectors",
            task="pipelines.image.generate_vectors",
            depends_on=["extract_multimodal"],
            timeout=120,
            max_retries=3,
        ),
        PipelineStep(
            name="index",
            task="pipelines.common.index",
            depends_on=["generate_vectors"],
            timeout=120,
        ),
    ]
}

VIDEO_PIPELINE = {
    "name": "video_ingest",
    "description": "视频RAG处理Pipeline (不含ASR)",
    "steps": [
        PipelineStep(
            name="preprocess",
            task="pipelines.video.preprocess",
            timeout=600,  # 视频转码耗时较长
            max_retries=2,
        ),
        # 双流并行处理
        PipelineStep(
            name="extract_keyframes",
            task="pipelines.video.extract_keyframes",
            depends_on=["preprocess"],
            timeout=300,
        ),
        PipelineStep(
            name="describe_segments",
            task="pipelines.video.describe_segments",
            depends_on=["preprocess"],
            timeout=600,  # Vision API调用耗时
            max_retries=2,
        ),
        # 对齐 (依赖两个并行流)
        PipelineStep(
            name="align_temporal",
            task="pipelines.video.align_temporal",
            depends_on=["extract_keyframes", "describe_segments"],
            timeout=120,
        ),
        PipelineStep(
            name="embed",
            task="pipelines.video.embed",
            depends_on=["align_temporal"],
            timeout=300,
            max_retries=3,
        ),
        PipelineStep(
            name="index",
            task="pipelines.common.index",
            depends_on=["embed"],
            timeout=120,
        ),
    ]
}

LINK_PIPELINE = {
    "name": "link_ingest",
    "description": "链接RAG处理Pipeline",
    "steps": [
        PipelineStep(
            name="scrape",
            task="pipelines.link.scrape",
            timeout=60,
            max_retries=3,
            retry_backoff=True,
        ),
        PipelineStep(
            name="extract_content",
            task="pipelines.link.extract_content",
            depends_on=["scrape"],
            timeout=60,
        ),
        # 复用文档Pipeline的子步骤
        PipelineStep(
            name="chunk",
            task="pipelines.document.chunk",
            depends_on=["extract_content"],
            timeout=60,
        ),
        PipelineStep(
            name="embed",
            task="pipelines.common.embed",
            depends_on=["chunk"],
            timeout=180,
            max_retries=3,
        ),
        PipelineStep(
            name="index",
            task="pipelines.common.index",
            depends_on=["embed"],
            timeout=120,
        ),
    ]
}

AUDIO_PIPELINE = {
    "name": "audio_ingest",
    "description": "音频处理Pipeline (当前仅存储)",
    "steps": [
        PipelineStep(
            name="extract_metadata",
            task="pipelines.audio.extract_metadata",
            timeout=30,
        ),
        PipelineStep(
            name="store_only",
            task="pipelines.audio.store_only",
            depends_on=["extract_metadata"],
            timeout=60,
        ),
        # ASR相关步骤待后续迭代启用:
        # PipelineStep(name="preprocess_audio", task="...", depends_on=["extract_metadata"]),
        # PipelineStep(name="asr", task="...", depends_on=["preprocess_audio"]),
        # PipelineStep(name="diarization", task="...", depends_on=["asr"]),
        # PipelineStep(name="semantic_chunk", task="...", depends_on=["diarization"]),
        # PipelineStep(name="embed", task="pipelines.common.embed", depends_on=["semantic_chunk"]),
        # PipelineStep(name="index", task="pipelines.common.index", depends_on=["embed"]),
    ]
}
```

### 8.2 DAG依赖执行引擎

```python
# pipelines/executor.py

import asyncio
from typing import Dict, List, Set
from celery import chain, chord, group
from celery.result import AsyncResult

class PipelineExecutor:
    """
    Pipeline DAG执行引擎
    支持: 串行依赖、并行分支、汇聚点
    """
    
    def __init__(self):
        self.step_results: Dict[str, AsyncResult] = {}
        self.step_status: Dict[str, TaskStatus] = {}
    
    async def execute(self, pipeline_def: Dict, context: Dict) -> Dict:
        """
        执行Pipeline
        
        执行示例 (VIDEO_PIPELINE):
        
        preprocess
             │
             ├──► extract_keyframes ──┐
             │                        │
             └──► describe_segments ──┤
                                      │
                                      ▼
                               align_temporal
                                      │
                                      ▼
                                    embed
                                      │
                                      ▼
                                    index
        """
        steps = {s.name: s for s in pipeline_def["steps"]}
        
        # 拓扑排序确定执行顺序
        execution_order = self._topological_sort(steps)
        
        for step_name in execution_order:
            step = steps[step_name]
            
            # 检查依赖是否完成
            if step.depends_on:
                await self._wait_for_dependencies(step.depends_on)
                
                # 检查是否有依赖失败
                failed_deps = [
                    dep for dep in step.depends_on
                    if self.step_status.get(dep) == TaskStatus.FAILED
                ]
                if failed_deps:
                    if step.on_failure == "skip":
                        self.step_status[step_name] = TaskStatus.FAILED
                        continue
                    elif step.on_failure == "fallback" and step.fallback_task:
                        # 执行降级任务
                        pass
                    else:
                        raise DependencyError(f"依赖步骤失败: {failed_deps}")
            
            # 执行任务
            result = await self._execute_step(step, context)
            self.step_results[step_name] = result
            self.step_status[step_name] = TaskStatus.SUCCESS
        
        return {
            "status": "success",
            "step_results": {k: v.id for k, v in self.step_results.items()}
        }
    
    def _topological_sort(self, steps: Dict[str, PipelineStep]) -> List[str]:
        """拓扑排序，支持并行分支"""
        in_degree = {name: 0 for name in steps}
        graph = {name: [] for name in steps}
        
        for name, step in steps.items():
            for dep in (step.depends_on or []):
                graph[dep].append(name)
                in_degree[name] += 1
        
        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        
        while queue:
            # 同一层级可并行
            result.extend(queue)
            next_queue = []
            for node in queue:
                for neighbor in graph[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue
        
        if len(result) != len(steps):
            raise ValueError("Pipeline中存在循环依赖")
        
        return result
    
    async def _execute_step(self, step: PipelineStep, context: Dict) -> AsyncResult:
        """执行单个步骤，带超时和重试"""
        task_func = self._resolve_task(step.task)
        
        for attempt in range(step.max_retries + 1):
            try:
                # Celery异步执行
                result = task_func.apply_async(
                    args=[context],
                    time_limit=step.timeout,
                    soft_time_limit=step.timeout - 10,
                    countdown=self._calc_retry_delay(step, attempt),
                )
                
                # 等待完成 (带超时)
                await asyncio.wait_for(
                    self._wait_for_celery(result),
                    timeout=step.timeout + 30  # 缓冲
                )
                
                return result
                
            except asyncio.TimeoutError:
                self.step_status[step.name] = TaskStatus.TIMEOUT
                if attempt < step.max_retries:
                    continue
                raise PipelineTimeout(f"步骤 {step.name} 超时")
            except Exception as e:
                self.step_status[step.name] = TaskStatus.FAILED
                if attempt < step.max_retries:
                    continue
                raise PipelineError(f"步骤 {step.name} 失败: {e}")
    
    def _calc_retry_delay(self, step: PipelineStep, attempt: int) -> int:
        """计算重试延迟"""
        if not step.retry_backoff or attempt == 0:
            return 0
        delay = min(
            step.retry_delay * (2 ** (attempt - 1)),
            step.retry_backoff_max
        )
        return delay
```

### 8.3 超时与重试策略总表

| Pipeline | 步骤 | 超时(秒) | 最大重试 | 重试策略 | 失败处理 |
|----------|------|----------|----------|----------|----------|
| **文档** | parse | 120 | 2 | 固定延迟10s | 失败整个Pipeline |
| | extract_structure | 60 | 2 | 固定延迟10s | 失败整个Pipeline |
| | chunk | 60 | 2 | 固定延迟10s | 失败整个Pipeline |
| | embed | 180 | 3 | 指数退避(10s,20s,40s) | 失败整个Pipeline |
| | index | 120 | 3 | 指数退避(10s,20s,40s) | 失败整个Pipeline |
| **Excel** | parse_sheets | 120 | 2 | 固定延迟10s | 失败整个Pipeline |
| | extract_schema | 60 | 2 | 固定延迟10s | 失败整个Pipeline |
| | generate_chunks | 120 | 2 | 固定延迟10s | 失败整个Pipeline |
| | annotate_permissions | 60 | 2 | 固定延迟10s | 失败整个Pipeline |
| | embed/index | 同文档 | 同文档 | 同文档 | 同文档 |
| **图片** | preprocess | 60 | 2 | 固定延迟10s | 失败整个Pipeline |
| | extract_multimodal | 180 | 2 | 指数退避(10s,20s) | **跳过**(OCR失败不阻断) |
| | generate_vectors | 120 | 3 | 指数退避(10s,20s,40s) | 失败整个Pipeline |
| | index | 120 | — | — | — |
| **视频** | preprocess | 600 | 2 | 指数退避(30s,60s) | 失败整个Pipeline |
| | extract_keyframes | 300 | 2 | 指数退避(10s,20s) | 失败整个Pipeline |
| | describe_segments | 600 | 2 | 指数退避(30s,60s) | 失败整个Pipeline |
| | align_temporal | 120 | 2 | 固定延迟10s | 失败整个Pipeline |
| | embed | 300 | 3 | 指数退避(30s,60s,120s) | 失败整个Pipeline |
| | index | 120 | — | — | — |
| **链接** | scrape | 60 | 3 | 指数退避(10s,20s,40s) | 失败整个Pipeline |
| | extract_content | 60 | 2 | 固定延迟10s | 失败整个Pipeline |
| | chunk/embed/index | 同文档 | 同文档 | 同文档 | 同文档 |
| **音频** | extract_metadata | 30 | 2 | 固定延迟5s | 失败整个Pipeline |
| | store_only | 60 | 2 | 固定延迟5s | 失败整个Pipeline |

### 8.4 监控与告警

```python
# pipelines/monitoring.py

from prometheus_client import Counter, Histogram, Gauge

# 指标定义
pipeline_duration = Histogram(
    'rag_pipeline_duration_seconds',
    'Pipeline执行耗时',
    ['pipeline_name', 'modality']
)

pipeline_failures = Counter(
    'rag_pipeline_failures_total',
    'Pipeline失败次数',
    ['pipeline_name', 'step_name', 'failure_reason']
)

pipeline_retries = Counter(
    'rag_pipeline_retries_total',
    '任务重试次数',
    ['pipeline_name', 'step_name']
)

active_pipelines = Gauge(
    'rag_active_pipelines',
    '当前执行中的Pipeline数',
    ['modality']
)

chunk_production = Counter(
    'rag_chunks_produced_total',
    '生成的Chunk数量',
    ['modality', 'chunk_type']
)

# 告警规则 (Prometheus Alertmanager)
ALERT_RULES = """
groups:
  - name: pipeline_alerts
    rules:
      - alert: PipelineHighFailureRate
        expr: rate(rag_pipeline_failures_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Pipeline失败率过高"
          
      - alert: PipelineStepTimeout
        expr: rag_pipeline_duration_seconds{quantile="0.99"} > 600
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Pipeline步骤执行超时"
          
      - alert: QueueBacklog
        expr: celery_queue_length > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "任务队列积压"
"""
```

### 8.5 Pipeline编排架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Pipeline编排调度层                                   │
│                                                                             │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐     │
│  │ API Gateway     │      │ Ingest Service  │      │ Pipeline        │     │
│  │ (接收上传请求)   │ -->  │ (文件接收/校验  │ -->  │ Dispatcher      │     │
│  │                 │      │  /路由分发)     │      │ (DAG执行引擎)   │     │
│  └─────────────────┘      └─────────────────┘      └─────────────────┘     │
│                                                             │               │
│                                                             ▼               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Celery Worker集群                              │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │   │
│  │  │ Worker-1│ │ Worker-2│ │ Worker-3│ │ Worker-N│ │ GPU     │      │   │
│  │  │ (CPU:   │ │ (CPU:   │ │ (CPU:   │ │ (CPU:   │ │ Worker  │      │   │
│  │  │  文档   │ │  Excel  │ │  链接   │ │  通用)  │ │ (Vision│      │   │
│  │  │  解析)  │ │  解析)  │ │  抓取)  │ │         │ │ 推理)  │      │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘      │   │
│  │                                                                     │   │
│  │  队列路由:                                                          │   │
│  │  - queue.document  (优先级: 高, 并发: 10)                           │   │
│  │  - queue.excel     (优先级: 高, 并发: 10)                           │   │
│  │  - queue.image     (优先级: 中, 并发: 5)                            │   │
│  │  - queue.video     (优先级: 低, 并发: 3, GPU绑定)                   │   │
│  │  - queue.link      (优先级: 中, 并发: 5)                            │   │
│  │  - queue.audio     (优先级: 低, 并发: 5)                            │   │
│  │  - queue.embed     (优先级: 高, 并发: 20, GPU绑定)                  │   │
│  │  - queue.index     (优先级: 高, 并发: 15)                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                             │               │
│                                                             ▼               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      结果存储层                                     │   │
│  │  - Pipeline执行状态: Redis (实时查询)                               │   │
│  │  - Pipeline执行历史: PostgreSQL (审计追溯)                          │   │
│  │  - 死信队列: RabbitMQ DLX (失败任务重试/人工介入)                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 附录: Pipeline对比总表

| 维度 | 文档RAG | Excel RAG | 图片RAG | 视频RAG | 链接RAG | 音频RAG |
|------|---------|-----------|---------|---------|---------|---------|
| **输入格式** | PDF/DOCX/TXT | XLSX/CSV | JPG/PNG/WEBP | MP4/AVI/MOV | HTTP/URL | MP3/WAV/M4A |
| **核心解析** | pdfplumber/unstructured | openpyxl/pandas | Pillow/PaddleOCR | FFmpeg | Playwright | FFmpeg(仅元数据) |
| **AI模型** | — | — | minimax-m3(Vision) | minimax-m3(Vision) | — | 🚧待ASR |
| **分块粒度** | 段落/章节/表格 | 表/列/行/区域 | 整图/区域 | 15秒片段 | 段落/章节 | 🚧语义分块 |
| **Chunk类型** | 4种策略 | 4种类型 | 主Chunk+区域 | 时间对齐片段 | 复用文档 | 🚧待设计 |
| **向量类型** | Dense+Sparse | Dense+Sparse | visual+text+sparse | visual+text+sparse | Dense+Sparse | 🚧Dense+Sparse |
| **权限粒度** | 文档级/段落级 | 字段级(involved_columns) | 文档级 | 文档级 | 文档级 | 🚧文档级 |
| **时间戳** | 页码 | 行号 | — | ✅ 秒级 | — | 🚧 秒级 |
| **双向量** | ❌ | ❌ | ✅ visual+text | ✅ visual+text | ❌ | 🚧待设计 |
| **处理复杂度** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| **典型超时** | 5-8min | 3-5min | 2-4min | 15-30min | 2-5min | <1min |
| **当前状态** | ✅ 可用 | ✅ 可用 | ✅ 可用 | ✅ 可用 | ✅ 可用 | 🚧 仅存储 |
