import {
  ArrowRightOutlined,
  AuditOutlined,
  BookOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  FileImageOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  FileSearchOutlined,
  HistoryOutlined,
  InboxOutlined,
  MenuOutlined,
  MedicineBoxOutlined,
  MessageOutlined,
  PlusOutlined,
  PaperClipOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SettingOutlined,
  StarFilled,
  StarOutlined,
  ThunderboltFilled,
  TeamOutlined,
} from '@ant-design/icons';
import { Bubble, Sender, ThoughtChain } from '@ant-design/x';
import { XMarkdown } from '@ant-design/x-markdown';
import '@ant-design/x-markdown/themes/light.css';
import { Input, Modal } from 'antd';
import { Button, ConfigProvider, Tag, Tooltip } from 'antd';
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';

import type { StoredSession } from './storage/sessionStore';

import type { AgentPatientContext, ApprovalUiData } from './api/types';
import { ApprovalCard } from './components/ApprovalCard';
import { FeedbackActions } from './components/FeedbackActions';
import { NotificationCenter } from './components/NotificationCenter';
import { TokenGate } from './components/TokenGate';
import { useAgentConversation } from './hooks/useAgentConversation';

const promptIdeas = [
  '糖尿病有哪些并发症？',
  '头痛、发热、咳嗽可能是什么病？',
  '二甲双胍的副作用和禁忌是什么？',
  '高血压应该挂什么科？',
];

const EChartPanel = lazy(() =>
  import('./components/EChartPanel').then((module) => ({ default: module.EChartPanel })),
);

const KnowledgeGraph = lazy(() =>
  import('./components/KnowledgeGraph').then((module) => ({ default: module.KnowledgeGraph })),
);

const AccessManagement = lazy(() =>
  import('./components/AccessManagement').then((module) => ({ default: module.AccessManagement })),
);

const ApprovalCenter = lazy(() =>
  import('./components/ApprovalCenter').then((module) => ({ default: module.ApprovalCenter })),
);

const ClinicalWorkspace = lazy(() =>
  import('./components/ClinicalWorkspace').then((module) => ({ default: module.ClinicalWorkspace })),
);

const KnowledgeAdmin = lazy(() =>
  import('./components/KnowledgeAdmin').then((module) => ({ default: module.KnowledgeAdmin })),
);

export function App() {
  const [accessToken, setAccessToken] = useState(() => window.__YUANQI_AUTH__?.accessToken || '');

  if (!accessToken) return <TokenGate onUnlock={setAccessToken} />;

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1a73e8',
          colorInfo: '#1a73e8',
          colorText: '#0d1b2a',
          colorBgBase: '#f4f6f9',
          colorBorder: '#cdd5de',
          borderRadius: 10,
          fontFamily:
            'Aptos, "Noto Sans SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif',
        },
      }}
    >
      <CopilotWorkspace accessToken={accessToken} onLock={() => setAccessToken('')} />
    </ConfigProvider>
  );
}

function CopilotWorkspace({ accessToken, onLock }: { accessToken: string; onLock: () => void }) {
  const [input, setInput] = useState('');
  const [conversationMode, setConversationMode] = useState<'knowledge' | 'report'>('knowledge');
  const [knowledgeOpen, setKnowledgeOpen] = useState(false);
  const [knowledgeQuery, setKnowledgeQuery] = useState('');
  const [sessionPanelOpen, setSessionPanelOpen] = useState(false);
  const [sessionQuery, setSessionQuery] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [patientContext, setPatientContext] = useState<AgentPatientContext | null>(null);
  const reportInputRef = useRef<HTMLInputElement>(null);
  const [activeView, setActiveView] = useState<'chat' | 'clinical' | 'kg' | 'knowledge-admin' | 'access' | 'approval'>('chat');
  const {
    turns, busy, sessions, currentSessionId,
    send, uploadReport, decide, cancel, clear, switchSession, newSession, deleteSession, updateSession,
  } = useAgentConversation(accessToken);
  const visibleSessions = useMemo(
    () => sessions
      .filter((session) => Boolean(session.archived) === showArchived)
      .filter((session) => session.title.toLocaleLowerCase().includes(sessionQuery.trim().toLocaleLowerCase()))
      .sort((left, right) => Number(Boolean(right.favorite)) - Number(Boolean(left.favorite)) || right.updatedAt - left.updatedAt),
    [sessions, sessionQuery, showArchived],
  );
  const waitingApproval = useMemo(
    () => turns.some((turn) => turn.uiData?.type === 'approval_card' && !turn.approvalDecision),
    [turns],
  );
  const hasError = turns.some((turn) => Boolean(turn.error));

  useEffect(() => {
    if (!sessionPanelOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSessionPanelOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [sessionPanelOpen]);

  const submit = (value: string) => {
    if (!value.trim()) return;
    setInput('');
    void send(
      value,
      conversationMode,
      conversationMode === 'knowledge' ? patientContext ?? undefined : undefined,
    );
  };

  const startBlankConversation = () => {
    if (busy) return;
    setPatientContext(null);
    setConversationMode('knowledge');
    clear();
  };

  const openPatientAssistant = (context: AgentPatientContext) => {
    if (busy) return;
    newSession();
    setPatientContext(context);
    setConversationMode('knowledge');
    setInput('');
    setSessionPanelOpen(false);
    setActiveView('chat');
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    return isToday
      ? d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      : d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="app-shell">
      <nav className="icon-rail" aria-label="主导航">
        <div className="brand-seal" aria-label="元启">
          元
        </div>
        <div className="rail-actions">
          <Tooltip title="新建会话" placement="right">
            <button className="rail-button" onClick={startBlankConversation} aria-label="新建会话">
              <PlusOutlined />
            </button>
          </Tooltip>
          <Tooltip title="医学对话" placement="right">
            <button
              className={`rail-button ${activeView === 'chat' ? 'rail-button--active' : ''}`}
              aria-label="医学对话"
              onClick={() => {
                setPatientContext(null);
                setActiveView('chat');
                setSessionPanelOpen(false);
              }}
            >
              <MessageOutlined />
            </button>
          </Tooltip>
          <Tooltip title="医学知识中心" placement="right">
            <button
              className={`rail-button ${activeView === 'kg' ? 'rail-button--active' : ''}`}
              aria-label="医学知识中心"
              onClick={() => { setActiveView('kg'); setSessionPanelOpen(false); }}
            >
              <FileSearchOutlined />
            </button>
          </Tooltip>
          <Tooltip title="患者业务工作台" placement="right">
            <button
              className={`rail-button ${activeView === 'clinical' ? 'rail-button--active' : ''}`}
              aria-label="患者业务工作台"
              onClick={() => { setActiveView('clinical'); setSessionPanelOpen(false); }}
            >
              <MedicineBoxOutlined />
            </button>
          </Tooltip>
          <Tooltip title="知识维护与发布" placement="right">
            <button
              className={`rail-button ${activeView === 'knowledge-admin' ? 'rail-button--active' : ''}`}
              aria-label="知识维护与发布"
              onClick={() => { setActiveView('knowledge-admin'); setSessionPanelOpen(false); }}
            >
              <DatabaseOutlined />
            </button>
          </Tooltip>
          <Tooltip title="会话历史" placement="right">
            <button
              className={`rail-button ${sessionPanelOpen ? 'rail-button--active' : ''}`}
              aria-label="会话历史"
              onClick={() => setSessionPanelOpen(!sessionPanelOpen)}
            >
              <HistoryOutlined />
            </button>
          </Tooltip>
          <Tooltip title="人员与数据授权" placement="right">
            <button
              className={`rail-button ${activeView === 'access' ? 'rail-button--active' : ''}`}
              aria-label="人员与数据授权"
              onClick={() => { setActiveView('access'); setSessionPanelOpen(false); }}
            >
              <TeamOutlined />
            </button>
          </Tooltip>
          <Tooltip title="审批与审计中心" placement="right">
            <button
              className={`rail-button ${activeView === 'approval' ? 'rail-button--active' : ''}`}
              aria-label="审批与审计中心"
              onClick={() => { setActiveView('approval'); setSessionPanelOpen(false); }}
            >
              <AuditOutlined />
            </button>
          </Tooltip>
        </div>
        <Tooltip title="清除凭证并锁定" placement="right">
          <button className="rail-button rail-lock" onClick={onLock} aria-label="锁定工作台">
            <SettingOutlined />
          </button>
        </Tooltip>
      </nav>

      {sessionPanelOpen && (
        <>
        <button
          className="session-panel-backdrop"
          aria-label="关闭会话历史"
          onClick={() => setSessionPanelOpen(false)}
        />
        <aside className="session-panel" aria-label="会话历史" aria-modal="true" role="dialog">
          <div className="session-panel-header">
            <div>
              <strong>会话历史</strong>
              <span>{sessions.length > 0 ? `${sessions.length} 个会话` : '最近的医学问答'}</span>
            </div>
            <button className="session-panel-close" onClick={() => setSessionPanelOpen(false)} aria-label="关闭会话历史">✕</button>
          </div>
          <div className="session-list">
            <div className="session-tools">
              <Input
                allowClear
                value={sessionQuery}
                prefix={<SearchOutlined />}
                placeholder="搜索会话标题"
                onChange={(event) => setSessionQuery(event.target.value)}
              />
              <Button
                type={showArchived ? 'primary' : 'default'}
                icon={<InboxOutlined />}
                onClick={() => setShowArchived((current) => !current)}
              >
                {showArchived ? '返回会话' : '已归档'}
              </Button>
            </div>
            {visibleSessions.length === 0 ? (
              <div className="session-empty">
                <MessageOutlined aria-hidden="true" />
                <strong>还没有历史会话</strong>
                <p>提出第一个医学问题后，会话会保存在这里。</p>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => {
                    setPatientContext(null);
                    newSession();
                    setSessionPanelOpen(false);
                  }}
                >
                  新建会话
                </Button>
              </div>
            ) : (
              visibleSessions.map((s: StoredSession) => (
                <div
                  key={s.id}
                  className={`session-item ${s.id === currentSessionId ? 'session-item--active' : ''}`}
                  onClick={() => {
                    setPatientContext(null);
                    switchSession(s.id);
                    setSessionPanelOpen(false);
                  }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      setPatientContext(null);
                      switchSession(s.id);
                      setSessionPanelOpen(false);
                    }
                  }}
                >
                  <div className="session-item-content">
                    <span className="session-item-title">{s.title}</span>
                    <span className="session-item-time">{formatTime(s.updatedAt)}</span>
                  </div>
                  <button
                    className="session-item-delete"
                    onClick={(e) => { e.stopPropagation(); updateSession(s.id, { favorite: !s.favorite }); }}
                    aria-label={s.favorite ? `取消收藏 ${s.title}` : `收藏 ${s.title}`}
                  >
                    {s.favorite ? <StarFilled /> : <StarOutlined />}
                  </button>
                  <button
                    className="session-item-delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      const title = window.prompt('修改会话标题', s.title)?.trim();
                      if (title) updateSession(s.id, { title: title.slice(0, 80) });
                    }}
                    aria-label={`重命名会话 ${s.title}`}
                  >
                    <EditOutlined />
                  </button>
                  <button
                    className="session-item-delete"
                    onClick={(e) => { e.stopPropagation(); updateSession(s.id, { archived: !s.archived }); }}
                    aria-label={s.archived ? `恢复会话 ${s.title}` : `归档会话 ${s.title}`}
                  >
                    <InboxOutlined />
                  </button>
                  <button
                    className="session-item-delete"
                    onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                    aria-label={`删除会话 ${s.title}`}
                  >
                    <DeleteOutlined />
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>
        </>
      )}

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-title">
            <button className="mobile-menu" aria-label="打开会话历史" onClick={() => setSessionPanelOpen(true)}>
              <MenuOutlined />
            </button>
            <div>
              <span>智能医疗协作台</span>
              <h1>{activeView === 'kg' ? '医学知识中心' : activeView === 'clinical' ? '患者健康工作台' : activeView === 'knowledge-admin' ? '知识维护与发布' : activeView === 'access' ? '人员与数据授权' : activeView === 'approval' ? '审批与审计中心' : conversationMode === 'report' ? '检查报告解读' : '医学智能问答'}</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <Tag className="scope-tag" icon={<SafetyCertificateOutlined />}>
              身份已验证 · 数据按权限访问
            </Tag>
            <NotificationCenter accessToken={accessToken} />
            <Button
              type="text"
              shape="circle"
              icon={<DeleteOutlined />}
              disabled={busy || turns.length === 0}
              onClick={startBlankConversation}
              aria-label="清空当前会话"
            />
          </div>
        </header>

        {activeView === 'kg' ? (
          <div className="kg-page">
            <Suspense fallback={<div className="kg-loading">加载知识图谱...</div>}>
              <KnowledgeGraph accessToken={accessToken} onOpenGovernance={() => setActiveView('knowledge-admin')} />
            </Suspense>
          </div>
        ) : activeView === 'clinical' ? (
          <Suspense fallback={<div className="access-loading">加载患者业务工作台...</div>}>
            <ClinicalWorkspace
              accessToken={accessToken}
              assistantDisabled={busy}
              onOpenAssistant={openPatientAssistant}
            />
          </Suspense>
        ) : activeView === 'knowledge-admin' ? (
          <Suspense fallback={<div className="access-loading">加载知识治理中心...</div>}>
            <KnowledgeAdmin accessToken={accessToken} />
          </Suspense>
        ) : activeView === 'access' ? (
          <Suspense fallback={<div className="access-loading">加载访问管理...</div>}>
            <AccessManagement accessToken={accessToken} />
          </Suspense>
        ) : activeView === 'approval' ? (
          <Suspense fallback={<div className="access-loading">加载审批中心...</div>}>
            <ApprovalCenter accessToken={accessToken} />
          </Suspense>
        ) : (<>
        <div className="conversation-scroll">
          <div className="conversation-stage">
            {turns.length === 0 ? (
              <WelcomePanel
                onChoose={(value) => {
                  setConversationMode('knowledge');
                  setInput(value);
                }}
                onSearchKnowledge={() => setKnowledgeOpen(true)}
                onUploadReport={() => {
                  setPatientContext(null);
                  setConversationMode('report');
                  reportInputRef.current?.click();
                }}
                onOpenPatient={() => setActiveView('clinical')}
              />
            ) : (
              <section className="message-list" aria-live="polite">
                {turns.map((turn) => (
                  <article className={`message-row message-row--${turn.role}`} key={turn.id}>
                    <Bubble
                      placement={turn.role === 'user' ? 'end' : 'start'}
                      variant={turn.role === 'user' ? 'filled' : 'borderless'}
                      shape="corner"
                      streaming={turn.streaming}
                      content={
                        turn.role === 'user' ? (
                          turn.attachment ? (
                            <ReportAttachmentCard attachment={turn.attachment} />
                          ) : turn.content
                        ) : (
                          <div className="assistant-content">
                            {turn.reasoning.length > 0 && (
                              <div className="reasoning-panel">
                                <div className="reasoning-label">
                                  <ThunderboltFilled /> 可公开执行轨迹
                                </div>
                                <ThoughtChain
                                  line="dashed"
                                  items={turn.reasoning.map((reasoning, index) => ({
                                    key: `${turn.id}-${index}`,
                                    title: reasoning,
                                    status:
                                      turn.streaming && index === turn.reasoning.length - 1
                                        ? 'loading'
                                        : 'success',
                                  }))}
                                />
                              </div>
                            )}
                            {turn.content && (
                              <XMarkdown
                                className="x-markdown-light yuanqi-markdown"
                                content={turn.content}
                                escapeRawHtml
                                openLinksInNewTab
                                streaming={{
                                  hasNextChunk: turn.streaming,
                                  enableAnimation: true,
                                  tail: turn.streaming,
                                }}
                              />
                            )}
                            {turn.uiData?.type === 'chart' && (
                              <Suspense fallback={<div className="chart-loading">正在加载图表组件…</div>}>
                                <EChartPanel data={turn.uiData} />
                              </Suspense>
                            )}
                            {turn.uiData?.type === 'approval_card' && (
                              <ApprovalCard
                                data={turn.uiData}
                                accessToken={accessToken}
                                disabled={busy}
                                decision={turn.approvalDecision}
                                status={turn.status}
                                onDecision={(approved, comment) =>
                                  decide(
                                    turn.id,
                                    (turn.uiData as ApprovalUiData).threadId,
                                    approved,
                                    comment,
                                  )
                                }
                              />
                            )}
                            {turn.error && (
                              <div className="message-error" role="alert">
                                <strong>任务未完成</strong>
                                <span>{turn.error}</span>
                              </div>
                            )}
                            {!turn.streaming && !turn.error && turn.content && currentSessionId && (
                              <FeedbackActions
                                accessToken={accessToken}
                                sessionId={currentSessionId}
                                turnId={turn.id}
                              />
                            )}
                          </div>
                        )
                      }
                    />
                  </article>
                ))}
              </section>
            )}
          </div>
        </div>

        <footer className="composer-wrap">
          <div className="composer-toolbar">
            <div className="composer-context">
              <span className={`context-dot context-dot--${conversationMode}`} />
              {conversationMode === 'report'
                ? '检查报告解读'
                : patientContext
                  ? '患者协作'
                  : '医学知识咨询'}
              {conversationMode === 'knowledge' && patientContext && (
                <Tag
                  className="composer-patient-tag"
                  closable={!busy && !waitingApproval}
                  onClose={(event) => {
                    event.preventDefault();
                    setPatientContext(null);
                  }}
                >
                  {patientContext.name} · {patientContext.patientNo}
                </Tag>
              )}
            </div>
            <div className="report-upload-row">
              <input
                ref={reportInputRef}
                type="file"
                hidden
                accept=".pdf,.txt,.csv,.jpg,.jpeg,.png,application/pdf,text/plain,text/csv,image/jpeg,image/png"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = '';
                  if (file) {
                    setPatientContext(null);
                    setConversationMode('report');
                    void uploadReport(file);
                  }
                }}
              />
              <Button
                type="text"
                size="small"
                icon={<PaperClipOutlined />}
                disabled={busy}
                onClick={() => {
                  setPatientContext(null);
                  reportInputRef.current?.click();
                }}
              >
                上传检查报告
              </Button>
              <span className="report-format-note">PDF / 图片 / TXT / CSV · ≤10 MB</span>
            </div>
            <span className="composer-boundary">
              {conversationMode === 'report'
                ? '仅使用本次报告与主动补充信息 · 原文件默认不保存'
                : patientContext
                  ? '仅操作当前患者 · 医生与科室由服务端身份写入'
                : '查询医学知识 · 不访问患者数据'}
            </span>
          </div>
          <Sender
            value={input}
            loading={busy}
            placeholder={patientContext
              ? `为${patientContext.name}录入病历、开具处方，或查询医学知识…`
              : '描述症状、查询疾病、药物信息或问该挂什么科…'}
            onChange={setInput}
            onSubmit={submit}
            onCancel={cancel}
          />
          <p className="composer-hint">医学信息仅供参考，不构成诊疗建议；如有健康问题请咨询专业医生。</p>
        </footer>
        </>
        )}
      </main>

      <Modal
        title="🔍 医学知识搜索"
        open={knowledgeOpen}
        onCancel={() => { setKnowledgeOpen(false); setKnowledgeQuery(''); }}
        footer={null}
        width={480}
      >
        <p style={{ marginBottom: 12, color: '#666', fontSize: 13 }}>
          输入疾病、症状、药物名称，从医学知识图谱中检索关联信息。
        </p>
        <Input.Search
          size="large"
          placeholder="例如：糖尿病、头痛、阿莫西林"
          enterButton="搜索"
          value={knowledgeQuery}
          onChange={(e) => setKnowledgeQuery(e.target.value)}
          onSearch={(value) => {
            if (value.trim()) {
              setInput(value.trim());
              setKnowledgeOpen(false);
              setKnowledgeQuery('');
              setConversationMode('knowledge');
              void send(value.trim(), 'knowledge');
            }
          }}
        />
      </Modal>
    </div>
  );
}

function WelcomePanel({
  onChoose,
  onSearchKnowledge,
  onUploadReport,
  onOpenPatient,
}: {
  onChoose: (value: string) => void;
  onSearchKnowledge: () => void;
  onUploadReport: () => void;
  onOpenPatient: () => void;
}) {
  return (
    <section className="welcome-panel">
      <p className="eyebrow">元启 · 安全医学协作</p>
      <h2>
        从问题出发，
        <br />
        选择正确的医疗路径。
      </h2>
      <p className="welcome-copy">
        查询医学知识、解读检查报告，或进入受权限保护的患者工作区。每条路径使用不同的数据边界，不会混用。
      </p>
      <div className="care-paths" aria-label="可用功能">
        <article className="care-path care-path--knowledge">
          <div className="care-path-icon"><BookOutlined /></div>
          <div className="care-path-copy">
            <span>公开医学知识</span>
            <h3>医学智能问答</h3>
            <p>查询疾病、症状、药物、检查和就诊科室，回答附带来源与安全边界。</p>
          </div>
          <button onClick={onSearchKnowledge}>
            开始查询 <ArrowRightOutlined />
          </button>
          <small>不访问患者数据</small>
        </article>
        <article className="care-path care-path--report">
          <div className="care-path-icon"><FileSearchOutlined /></div>
          <div className="care-path-copy">
            <span>个人报告上下文</span>
            <h3>检查报告解读</h3>
            <p>上传 PDF、图片或表格，分层解释异常指标，并通过对话补充健康信息。</p>
          </div>
          <button onClick={onUploadReport}>
            上传报告 <ArrowRightOutlined />
          </button>
          <small>默认不保存原文件</small>
        </article>
        <article className="care-path care-path--patient">
          <div className="care-path-icon"><MedicineBoxOutlined /></div>
          <div className="care-path-copy">
            <span>受保护业务数据</span>
            <h3>患者健康工作台</h3>
            <p>管理患者、病历与处方；每次读取按当前身份执行行级授权并记录操作。</p>
          </div>
          <button onClick={onOpenPatient}>
            进入工作台 <ArrowRightOutlined />
          </button>
          <small><SafetyCertificateOutlined /> 仅限授权人员</small>
        </article>
      </div>
      <div className="welcome-section-heading">
        <span>可以这样开始</span>
        <p>选择一个问题，仍可在输入框中继续修改。</p>
      </div>
      <div className="prompt-ledger" aria-label="建议问题">
        {promptIdeas.map((prompt, index) => (
          <button key={prompt} onClick={() => onChoose(prompt)}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{prompt}</strong>
            <PlusOutlined />
          </button>
        ))}
      </div>
      <div className="welcome-boundaries">
        <span>知识回答提供来源</span>
        <span>报告解读不替代诊断</span>
        <span>患者访问全程受控</span>
      </div>
    </section>
  );
}

function ReportAttachmentCard({
  attachment,
}: {
  attachment: NonNullable<import('./hooks/useAgentConversation').ConversationTurn['attachment']>;
}) {
  const isPdf = attachment.mediaType === 'application/pdf';
  const isImage = attachment.mediaType.startsWith('image/');
  const statusText = attachment.status === 'uploading'
    ? '正在上传并解析'
    : attachment.status === 'analyzed'
      ? '已完成解析'
      : '解析失败';
  return (
    <div className={`report-attachment report-attachment--${attachment.status}`}>
      <div className="report-attachment-icon">
        {isPdf ? <FilePdfOutlined /> : isImage ? <FileImageOutlined /> : <FileTextOutlined />}
      </div>
      <div className="report-attachment-main">
        <strong title={attachment.name}>{attachment.name}</strong>
        <span>{formatFileSize(attachment.size)} · {attachment.mediaType}</span>
      </div>
      <div className="report-attachment-status">
        {attachment.status === 'analyzed'
          ? <CheckCircleOutlined />
          : attachment.status === 'failed'
            ? <CloseCircleOutlined />
            : <span className="report-upload-spinner" />}
        {statusText}
      </div>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
