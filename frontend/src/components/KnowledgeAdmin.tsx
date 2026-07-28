import { CheckOutlined, CloudUploadOutlined, DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined, StopOutlined, UndoOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Form, Input, Modal, Pagination, Select, Space, Table, Tag, message } from 'antd';
import { useCallback, useEffect, useState } from 'react';

import { normalizeAccessToken } from '../api/auth';

interface Document {
  id: number;
  documentKey: string;
  title: string;
  entityType: string;
  content: string;
  sourceUri?: string;
  status: 'DRAFT' | 'REVIEW' | 'PUBLISHED' | 'RETIRED';
  knowledgeVersion: number;
  publishedAt?: string;
  updatedAt: string;
}
interface PageData {
  content: Document[];
  page: number;
  size: number;
  totalElements: number;
}
interface IndexVersion {
  id: number;
  versionName: string;
  collectionName: string;
  status: string;
  documentCount: number;
  createdAt: string;
}

export function KnowledgeAdmin({ accessToken }: { accessToken: string }) {
  const [data, setData] = useState<PageData | null>(null);
  const [versions, setVersions] = useState<IndexVersion[]>([]);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState('ALL');
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<Document | 'new' | null>(null);
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [form] = Form.useForm();
  const headers = useCallback(() => ({
    Authorization: `Bearer ${normalizeAccessToken(accessToken)}`,
    'Content-Type': 'application/json',
  }), [accessToken]);

  const load = useCallback(async () => {
    setLoading(true);
    const query = new URLSearchParams({ page: String(page), size: '15', status });
    if (keyword.trim()) query.set('keyword', keyword.trim());
    try {
      const response = await fetch(`/api/v1/knowledge-documents?${query}`, { headers: headers() });
      if (response.status === 403) { setForbidden(true); return; }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setData((await response.json()).data);
      const versionResponse = await fetch('/api/v1/knowledge-index-versions', { headers: headers() });
      if (versionResponse.ok) setVersions((await versionResponse.json()).data ?? []);
      setForbidden(false);
    } catch {
      message.error('知识文档加载失败');
    } finally {
      setLoading(false);
    }
  }, [headers, keyword, page, status]);
  useEffect(() => { void load(); }, [load]);

  const openEditor = (document?: Document) => {
    form.setFieldsValue(document ?? {
      documentKey: `medical:${Date.now()}`,
      entityType: 'Guideline',
      sourceUri: '',
    });
    setEditing(document ?? 'new');
  };

  const save = async () => {
    const values = await form.validateFields();
    const response = await fetch(
      editing === 'new' ? '/api/v1/knowledge-documents' : `/api/v1/knowledge-documents/${(editing as Document).id}`,
      {
        method: editing === 'new' ? 'POST' : 'PUT',
        headers: { ...headers(), 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify(values),
      },
    );
    if (!response.ok) { message.error(`保存失败（HTTP ${response.status}）`); return; }
    message.success('知识文档已保存为草稿');
    setEditing(null);
    await load();
  };

  const transition = async (document: Document, action: 'submit' | 'publish' | 'retire' | 'reject' | 'restore') => {
    const response = await fetch(`/api/v1/knowledge-documents/${document.id}/${action}`, {
      method: 'PATCH',
      headers: { ...headers(), 'Idempotency-Key': crypto.randomUUID() },
    });
    if (!response.ok) { message.error(`操作失败（HTTP ${response.status}）`); return; }
    message.success(action === 'publish' ? '知识版本已发布，可进入索引流程' : '知识状态已更新');
    await load();
  };

  const deleteDocument = (document: Document) => {
    Modal.confirm({
      title: '确认删除知识文档？',
      content: '删除后将从维护列表隐藏，并在下次重建索引时从向量检索中移除；治理记录仍会保留。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        const response = await fetch(`/api/v1/knowledge-documents/${document.id}`, {
          method: 'DELETE',
          headers: { ...headers(), 'Idempotency-Key': crypto.randomUUID() },
        });
        if (!response.ok) { message.error(`删除失败（HTTP ${response.status}）`); return; }
        message.success('知识文档已删除；请重建向量索引以同步检索内容');
        await load();
      },
    });
  };

  const rebuildIndex = async () => {
    setIndexing(true);
    try {
      const response = await fetch('/api/v1/kg/index/rebuild', {
        method: 'POST',
        headers: { ...headers(), 'Idempotency-Key': crypto.randomUUID(), 'X-Trace-Id': crypto.randomUUID() },
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message ?? `HTTP ${response.status}`);
      message.success(`索引 ${payload.version} 已激活，共 ${payload.documentCount} 篇文档`);
    } catch (cause) {
      message.error(cause instanceof Error ? cause.message : '索引重建失败');
    } finally {
      setIndexing(false);
    }
  };

  if (forbidden) return (
    <div className="knowledge-admin-page">
      <Alert showIcon type="info" title="当前账号没有知识治理权限" description="需要 knowledge:manage、knowledge:publish 或 knowledge:index 权限。" />
    </div>
  );

  return (
    <div className="knowledge-admin-page">
      <Alert
        showIcon
        type="warning"
        title="知识库仍处于试运行治理阶段"
        description="仅展示经过来源核验、人工送审并发布的内容；来源不足 200 字或缺少 HTTPS 权威出处的文档不能进入审核。"
      />
      <section className="clinical-hero">
        <div><span>KNOWLEDGE GOVERNANCE</span><h2>医学知识维护与发布</h2><p>草稿、审核、发布和停用全程保留版本与发布人。</p></div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
          <Button icon={<CloudUploadOutlined />} loading={indexing} onClick={() => void rebuildIndex()}>重建向量索引</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor()}>新建知识</Button>
        </Space>
      </section>
      <Card>
        <div className="approval-filters">
          <Input.Search allowClear value={keyword} placeholder="搜索标题或文档键" onChange={(event) => setKeyword(event.target.value)} onSearch={() => { setPage(0); void load(); }} />
          <Select value={status} onChange={(value) => { setStatus(value); setPage(0); }} options={['ALL', 'DRAFT', 'REVIEW', 'PUBLISHED', 'RETIRED'].map((value) => ({ value, label: value }))} />
        </div>
        <Table
          rowKey="id"
          loading={loading}
          pagination={false}
          dataSource={data?.content ?? []}
          scroll={{ x: 1040 }}
          columns={[
            { title: '文档', render: (_, item) => <div><strong>{item.title}</strong><small className="table-secondary">{item.documentKey}</small></div> },
            { title: '类型', dataIndex: 'entityType' },
            {
              title: '权威来源',
              dataIndex: 'sourceUri',
              render: (value) => value
                ? <a href={value} target="_blank" rel="noreferrer">查看原文</a>
                : <Tag color="red">缺少来源</Tag>,
            },
            { title: '版本', dataIndex: 'knowledgeVersion', render: (value) => `v${value}` },
            { title: '状态', dataIndex: 'status', render: (value) => <Tag color={statusColor(value)}>{value}</Tag> },
            { title: '更新时间', dataIndex: 'updatedAt', render: (value) => new Date(value).toLocaleString('zh-CN') },
            {
              title: '操作',
              fixed: 'right',
              render: (_, item) => <Space wrap>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEditor(item)}>编辑</Button>
                {item.status === 'DRAFT' && <Button size="small" icon={<CloudUploadOutlined />} onClick={() => void transition(item, 'submit')}>送审</Button>}
                {item.status === 'REVIEW' && <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => void transition(item, 'publish')}>发布</Button>}
                {item.status === 'REVIEW' && <Button size="small" onClick={() => void transition(item, 'reject')}>退回</Button>}
                {item.status === 'PUBLISHED' && <Button size="small" danger icon={<StopOutlined />} onClick={() => void transition(item, 'retire')}>停用</Button>}
                {item.status === 'RETIRED' && <Button size="small" type="primary" icon={<UndoOutlined />} onClick={() => void transition(item, 'restore')}>重新启用</Button>}
                {(item.status === 'DRAFT' || item.status === 'RETIRED') && <Button size="small" danger icon={<DeleteOutlined />} onClick={() => deleteDocument(item)}>删除</Button>}
              </Space>,
            },
          ]}
        />
        <Pagination current={(data?.page ?? 0) + 1} pageSize={data?.size ?? 15} total={data?.totalElements ?? 0} onChange={(value) => setPage(value - 1)} />
      </Card>
      <Card title="向量索引版本">
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          dataSource={versions}
          columns={[
            { title: '版本', dataIndex: 'versionName' },
            { title: '集合', dataIndex: 'collectionName' },
            { title: '文档数', dataIndex: 'documentCount' },
            { title: '状态', dataIndex: 'status', render: (value) => <Tag color={value === 'ACTIVE' ? 'green' : value === 'FAILED' ? 'red' : 'gold'}>{value}</Tag> },
            { title: '创建时间', dataIndex: 'createdAt', render: (value) => new Date(value).toLocaleString('zh-CN') },
          ]}
        />
      </Card>
      <Modal open={Boolean(editing)} width={760} title={editing === 'new' ? '新建知识文档' : '编辑知识文档'} okText="保存草稿" onCancel={() => setEditing(null)} onOk={() => void save()}>
        <Form form={form} layout="vertical">
          <div className="form-grid">
            <Form.Item name="documentKey" label="文档键" rules={[{ required: true, pattern: /^[A-Za-z0-9:_-]+$/ }]}><Input disabled={editing !== 'new'} /></Form.Item>
            <Form.Item name="title" label="标题" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="entityType" label="实体类型" rules={[{ required: true }]}><Select options={['Disease', 'Symptom', 'Drug', 'Department', 'Exam', 'Guideline'].map((value) => ({ value }))} /></Form.Item>
            <Form.Item name="sourceUri" label="权威来源地址" rules={[{ required: true, type: 'url' }]}><Input placeholder="https://..." /></Form.Item>
          </div>
          <Form.Item name="content" label="知识正文" rules={[{ required: true, min: 200, max: 20000 }]}><Input.TextArea rows={14} showCount maxLength={20000} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

function statusColor(status: string) {
  return status === 'PUBLISHED' ? 'green' : status === 'REVIEW' ? 'gold' : status === 'RETIRED' ? 'default' : 'blue';
}
