import {
  AuditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DownloadOutlined,
  PrinterOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { Alert, Button, Card, Checkbox, Empty, Input, Modal, Pagination, Select, Space, Spin, Tag, Timeline, message } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { normalizeAccessToken } from '../api/auth';

interface ApiEnvelope<T> {
  data: T;
  message: string;
}

interface PrescriptionTask {
  taskId: string;
  taskName: string;
  processInstanceId: string;
  createdAt: string;
  prescriptionId: number;
  targetStatus: 'DISPENSED' | 'CANCELLED';
  requesterId: number;
  reason: string;
}

interface AgentAuditEvent {
  id: number;
  actorName: string;
  traceId: string;
  toolName: string;
  phase: string;
  outcome: string;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  occurredAt: string;
}

interface DecisionTarget {
  task: PrescriptionTask;
  approved: boolean;
}

const workflowBase = '/api/v1/workflows/prescription-status-changes';

export function ApprovalCenter({ accessToken }: { accessToken: string }) {
  const [tasks, setTasks] = useState<PrescriptionTask[]>([]);
  const [audits, setAudits] = useState<AgentAuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [auditForbidden, setAuditForbidden] = useState(false);
  const [error, setError] = useState('');
  const [decision, setDecision] = useState<DecisionTarget | null>(null);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [taskQuery, setTaskQuery] = useState('');
  const [taskStatus, setTaskStatus] = useState<string>('ALL');
  const [selectedTasks, setSelectedTasks] = useState<string[]>([]);
  const [auditQuery, setAuditQuery] = useState('');
  const [auditRisk, setAuditRisk] = useState<string>('ALL');
  const [auditPage, setAuditPage] = useState(1);
  const [messageApi, contextHolder] = message.useMessage();
  const filteredTasks = useMemo(() => tasks.filter((task) =>
    (taskStatus === 'ALL' || task.targetStatus === taskStatus)
    && `${task.prescriptionId} ${task.requesterId} ${task.reason}`.toLocaleLowerCase()
      .includes(taskQuery.trim().toLocaleLowerCase()),
  ), [taskQuery, taskStatus, tasks]);
  const filteredAudits = useMemo(() => audits.filter((audit) =>
    (auditRisk === 'ALL' || audit.riskLevel === auditRisk)
    && `${audit.toolName} ${audit.actorName} ${audit.traceId} ${audit.outcome}`.toLocaleLowerCase()
      .includes(auditQuery.trim().toLocaleLowerCase()),
  ), [auditQuery, auditRisk, audits]);
  const auditPageSize = 10;
  const visibleAudits = filteredAudits.slice((auditPage - 1) * auditPageSize, auditPage * auditPageSize);

  const headers = useCallback(() => ({
    Authorization: `Bearer ${normalizeAccessToken(accessToken)}`,
    Accept: 'application/json',
  }), [accessToken]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const taskResponse = await fetch(`${workflowBase}/tasks/my`, { headers: headers() });
      if (!taskResponse.ok) throw new Error(await readError(taskResponse));
      const taskEnvelope = await taskResponse.json() as ApiEnvelope<PrescriptionTask[]>;
      setTasks(taskEnvelope.data);

      const auditResponse = await fetch('/api/v1/agent-audit/events?limit=50', { headers: headers() });
      if (auditResponse.status === 403) {
        setAuditForbidden(true);
        setAudits([]);
      } else if (!auditResponse.ok) {
        throw new Error(await readError(auditResponse));
      } else {
        const auditEnvelope = await auditResponse.json() as ApiEnvelope<AgentAuditEvent[]>;
        setAudits(auditEnvelope.data);
        setAuditForbidden(false);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法加载审批中心');
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    void load();
  }, [load]);

  const submitDecision = async () => {
    if (!decision) return;
    setSubmitting(true);
    try {
      const response = await fetch(
        `${workflowBase}/tasks/${encodeURIComponent(decision.task.taskId)}/decision`,
        {
          method: 'POST',
          headers: {
            ...headers(),
            'Content-Type': 'application/json',
            'Idempotency-Key': `prescription-decision-${crypto.randomUUID()}`,
          },
          body: JSON.stringify({ approved: decision.approved, comment: comment.trim() || null }),
        },
      );
      if (!response.ok) throw new Error(await readError(response));
      messageApi.success(decision.approved ? '处方状态变更已批准并执行' : '处方状态变更已驳回');
      setDecision(null);
      setComment('');
      await load();
    } catch (reason) {
      messageApi.error(reason instanceof Error ? reason.message : '审批提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  const submitOne = async (task: PrescriptionTask, approved: boolean, batchComment: string) => {
    const response = await fetch(
      `${workflowBase}/tasks/${encodeURIComponent(task.taskId)}/decision`,
      {
        method: 'POST',
        headers: {
          ...headers(),
          'Content-Type': 'application/json',
          'Idempotency-Key': `prescription-decision-${crypto.randomUUID()}`,
        },
        body: JSON.stringify({ approved, comment: batchComment || null }),
      },
    );
    if (!response.ok) throw new Error(await readError(response));
  };

  const batchDecision = (approved: boolean) => {
    const selected = tasks.filter((task) => selectedTasks.includes(task.taskId));
    if (selected.length === 0) return;
    Modal.confirm({
      title: `${approved ? '批量批准' : '批量驳回'} ${selected.length} 个审批任务？`,
      content: '每个任务仍会在 Java 业务层逐条复检权限、流程状态与业务状态。',
      okText: approved ? '逐条批准' : '逐条驳回',
      okButtonProps: { danger: !approved },
      async onOk() {
        setSubmitting(true);
        try {
          for (const task of selected) await submitOne(task, approved, '审批中心批量处理');
          messageApi.success(`已处理 ${selected.length} 个任务`);
          setSelectedTasks([]);
          await load();
        } finally {
          setSubmitting(false);
        }
      },
    });
  };

  const downloadReport = async (format: 'xlsx' | 'pdf') => {
    const response = await fetch(`/api/v1/agent-audit/reports/${format}?limit=100`, {
      headers: headers(),
    });
    if (!response.ok) {
      messageApi.error(await readError(response));
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = `yuanqi-agent-audit-${new Date().toISOString().slice(0, 10)}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="approval-center">
      {contextHolder}
      <div className="approval-center__heading">
        <div>
          <span>HUMAN-IN-THE-LOOP</span>
          <h2>审批与审计中心</h2>
          <p>处方状态只有在指定审批人确认后才会由 Java 业务层执行。</p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>
          刷新
        </Button>
      </div>

      {error && <Alert type="error" showIcon title="加载失败" description={error} />}
      {loading ? (
        <div className="approval-center__loading"><Spin size="large" /></div>
      ) : (
        <div className="approval-center__grid">
          <section>
            <h3>待我审批 <Tag color="blue">{tasks.length}</Tag></h3>
            <div className="approval-filters">
              <Input allowClear value={taskQuery} placeholder="搜索处方、申请人或原因" onChange={(event) => setTaskQuery(event.target.value)} />
              <Select
                value={taskStatus}
                onChange={setTaskStatus}
                options={[
                  { value: 'ALL', label: '全部动作' },
                  { value: 'DISPENSED', label: '发药' },
                  { value: 'CANCELLED', label: '取消' },
                ]}
              />
            </div>
            {selectedTasks.length > 0 && (
              <Card size="small" className="approval-batch-bar">
                <Space wrap>
                  <span>已选择 {selectedTasks.length} 项</span>
                  <Button type="primary" loading={submitting} onClick={() => batchDecision(true)}>批量批准</Button>
                  <Button danger loading={submitting} onClick={() => batchDecision(false)}>批量驳回</Button>
                </Space>
              </Card>
            )}
            {filteredTasks.length === 0 ? (
              <Card><Empty description="当前没有分配给你的处方审批任务" /></Card>
            ) : filteredTasks.map((task) => (
              <Card key={task.taskId} className="approval-task-card">
                <div className="approval-task-card__top">
                  <Checkbox
                    checked={selectedTasks.includes(task.taskId)}
                    onChange={(event) => setSelectedTasks((current) => event.target.checked
                      ? [...current, task.taskId]
                      : current.filter((id) => id !== task.taskId))}
                  />
                  <div>
                    <strong>处方 #{task.prescriptionId}</strong>
                    <span>{new Date(task.createdAt).toLocaleString('zh-CN')}</span>
                  </div>
                  <Tag color={task.targetStatus === 'DISPENSED' ? 'green' : 'red'}>
                    {task.targetStatus === 'DISPENSED' ? '发药' : '取消'}
                  </Tag>
                </div>
                <p>{task.reason}</p>
                <small>申请人 ID：{task.requesterId} · 流程：{task.processInstanceId}</small>
                <Space>
                  <Button
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    onClick={() => setDecision({ task, approved: true })}
                  >
                    同意
                  </Button>
                  <Button
                    danger
                    icon={<CloseCircleOutlined />}
                    onClick={() => setDecision({ task, approved: false })}
                  >
                    驳回
                  </Button>
                </Space>
              </Card>
            ))}
          </section>

          <section>
            <div className="approval-section-heading">
              <h3><AuditOutlined /> Agent 审计轨迹</h3>
              {!auditForbidden && (
                <Space>
                  <Button icon={<DownloadOutlined />} onClick={() => void downloadReport('xlsx')}>导出 XLSX</Button>
                  <Button icon={<PrinterOutlined />} onClick={() => void downloadReport('pdf')}>固定版式 PDF</Button>
                </Space>
              )}
            </div>
            {!auditForbidden && (
              <div className="approval-filters">
                <Input allowClear value={auditQuery} placeholder="搜索工具、人员、结果或 Trace" onChange={(event) => { setAuditQuery(event.target.value); setAuditPage(1); }} />
                <Select
                  value={auditRisk}
                  onChange={(value) => { setAuditRisk(value); setAuditPage(1); }}
                  options={['ALL', 'low', 'medium', 'high', 'critical'].map((value) => ({ value, label: value === 'ALL' ? '全部风险' : value }))}
                />
              </div>
            )}
            {auditForbidden ? (
              <Alert
                type="info"
                showIcon
                title="当前账号没有 agent:audit:read 权限"
                description="工具仍会写入审计台账；只有审计角色可以查看本院记录。"
              />
            ) : audits.length === 0 ? (
              <Card><Empty description="暂无 Agent 工具审计事件" /></Card>
            ) : (
              <Card>
                <Timeline
                  items={visibleAudits.map((audit) => ({
                    color: outcomeColor(audit.outcome),
                    children: (
                      <div className="audit-event">
                        <strong>{audit.toolName}</strong>
                        <Tag color={riskColor(audit.riskLevel)}>{audit.riskLevel}</Tag>
                        <p>{audit.phase} · {audit.outcome}</p>
                        <small>
                          {audit.actorName} · {new Date(audit.occurredAt).toLocaleString('zh-CN')}
                          <br />Trace: {audit.traceId}
                        </small>
                      </div>
                    ),
                  }))}
                />
                <Pagination
                  size="small"
                  current={auditPage}
                  pageSize={auditPageSize}
                  total={filteredAudits.length}
                  showSizeChanger={false}
                  onChange={setAuditPage}
                />
              </Card>
            )}
          </section>
        </div>
      )}

      <Modal
        open={Boolean(decision)}
        title={decision?.approved ? '确认批准处方状态变更' : '确认驳回处方状态变更'}
        okText={decision?.approved ? '批准并执行' : '确认驳回'}
        okButtonProps={{ danger: !decision?.approved, loading: submitting }}
        cancelText="取消"
        onCancel={() => { setDecision(null); setComment(''); }}
        onOk={() => void submitDecision()}
      >
        <p>
          处方 #{decision?.task.prescriptionId} 将
          {decision?.approved
            ? `变更为 ${decision.task.targetStatus}`
            : '保持当前状态，不执行任何业务写入'}。
        </p>
        <Input.TextArea
          value={comment}
          maxLength={1000}
          showCount
          rows={4}
          placeholder="填写审批意见（可选）"
          onChange={(event) => setComment(event.target.value)}
        />
      </Modal>
    </div>
  );
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { message?: unknown };
    if (typeof payload.message === 'string') return payload.message;
  } catch {
    // Use the status fallback below.
  }
  return `请求失败（HTTP ${response.status}）`;
}

function riskColor(risk: AgentAuditEvent['riskLevel']) {
  return risk === 'critical' ? 'red' : risk === 'high' ? 'orange' : risk === 'medium' ? 'gold' : 'blue';
}

function outcomeColor(outcome: string) {
  if (outcome === 'FAILED' || outcome === 'REJECTED') return 'red';
  if (outcome === 'SUCCEEDED' || outcome === 'APPROVED') return 'green';
  return 'blue';
}
