import { useCallback, useEffect, useRef, useState } from 'react';

import { analyzeMedicalReport, resumeAgentStream, startAgentStream } from '../api/client';
import type { AgentStreamEvent, AgentUiData, ReportAnalysis } from '../api/types';
import {
  createSession,
  deleteRemoteSession,
  deleteSession as deleteStoredSession,
  loadSession,
  loadSessions,
  loadRemoteSessions,
  patchSession,
  saveSession,
  saveRemoteSession,
  updateSessionTitle,
  type StoredSession,
} from '../storage/sessionStore';

export interface ConversationTurn {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  reasoning: string[];
  uiData?: AgentUiData;
  streaming: boolean;
  status?: string;
  error?: string;
  approvalDecision?: 'approved' | 'rejected';
  attachment?: {
    name: string;
    size: number;
    mediaType: string;
    status: 'uploading' | 'analyzed' | 'failed';
  };
}

export function useAgentConversation(accessToken: string) {
  const [sessions, setSessions] = useState<StoredSession[]>(() => loadSessions());
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(() => {
    const stored = loadSessions();
    return stored[0]?.id ?? null;
  });
  const [turns, setTurns] = useState<ConversationTurn[]>(() => {
    const stored = loadSessions();
    return stored[0]?.turns ?? [];
  });
  const [busy, setBusy] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);
  const currentSessionIdRef = useRef(currentSessionId);
  const syncTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => () => {
    activeRequest.current?.abort();
    if (syncTimer.current) clearTimeout(syncTimer.current);
  }, []);

  useEffect(() => {
    let active = true;
    void loadRemoteSessions(accessToken).then((remote) => {
      if (!active || remote.length === 0) return;
      remote.forEach(saveSession);
      const merged = loadSessions();
      setSessions(merged);
      const first = merged[0];
      if (first) {
        currentSessionIdRef.current = first.id;
        setCurrentSessionId(first.id);
        setTurns(first.turns);
      }
    }).catch(() => {
      // Offline use remains available; the next local update retries synchronization.
    });
    return () => { active = false; };
  }, [accessToken]);

  const queueRemoteSave = useCallback((session: StoredSession) => {
    if (syncTimer.current) clearTimeout(syncTimer.current);
    syncTimer.current = setTimeout(() => {
      void saveRemoteSession(accessToken, session).catch(() => undefined);
    }, 500);
  }, [accessToken]);

  // Persist turns whenever they change
  const persistTurns = useCallback(
    (updatedTurns: ConversationTurn[]) => {
      const sid = currentSessionIdRef.current;
      if (!sid || updatedTurns.length === 0) return;
      const existing = loadSession(sid);
      if (existing) {
        const updated = updateSessionTitle(existing, updatedTurns);
        saveSession(updated);
        queueRemoteSave(updated);
        setSessions(loadSessions());
      }
    },
    [queueRemoteSave],
  );

  const updateAssistant = useCallback(
    (id: string, updater: (turn: ConversationTurn) => ConversationTurn) => {
      setTurns((current) => {
        const updated = current.map((turn) => (turn.id === id ? updater(turn) : turn));
        persistTurns(updated);
        return updated;
      });
    },
    [persistTurns],
  );

  const consumeEvent = useCallback(
    (assistantId: string, event: AgentStreamEvent) => {
      updateAssistant(assistantId, (turn) => {
        switch (event.type) {
          case 'reasoning':
            return { ...turn, reasoning: [...turn.reasoning, event.reasoning] };
          case 'text':
            return { ...turn, content: turn.content + event.text };
          case 'uiData':
            return { ...turn, uiData: event.uiData };
          case 'tool_result':
            return { ...turn, content: turn.content + '\n\n' + event.toolResult.formatted };
          case 'done':
            return { ...turn, streaming: false, status: event.status };
          case 'error':
            return { ...turn, streaming: false, error: `${event.error.code} · ${event.error.message}` };
        }
      });
    },
    [updateAssistant],
  );

  const send = useCallback(
    async (message: string, mode: 'knowledge' | 'report' = 'knowledge') => {
      const normalized = message.trim();
      if (!normalized || busy) return;

      // Create a new session if none exists
      let sid = currentSessionIdRef.current;
      if (!sid) {
        const session = createSession([]);
        saveSession(session);
        queueRemoteSave(session);
        sid = session.id;
        currentSessionIdRef.current = sid;
        setCurrentSessionId(sid);
        setSessions(loadSessions());
      }

      const userId = crypto.randomUUID();
      const assistantId = crypto.randomUUID();
      const newTurns: ConversationTurn[] = [
        ...turns,
        { id: userId, role: 'user', content: normalized, reasoning: [], streaming: false },
        { id: assistantId, role: 'assistant', content: '', reasoning: [], streaming: true },
      ];
      setTurns(newTurns);

      const controller = new AbortController();
      activeRequest.current = controller;
      setBusy(true);
      try {
        await startAgentStream(
          {
            threadId: sid,
            mode,
            message: normalized,
            history: turns
              .filter((turn) => !turn.streaming && !turn.error && turn.content.trim())
              .slice(-12)
              .map((turn) => ({ role: turn.role, content: turn.content.slice(0, 8000) })),
          },
          accessToken,
          (event) => consumeEvent(assistantId, event),
          controller.signal,
        );
      } catch (error) {
        if (!controller.signal.aborted) {
          const msg = error instanceof Error ? error.message : '请求未完成';
          updateAssistant(assistantId, (turn) => ({ ...turn, streaming: false, error: msg }));
        }
      } finally {
        activeRequest.current = null;
        setBusy(false);
      }
    },
    [accessToken, busy, consumeEvent, queueRemoteSave, updateAssistant, turns],
  );

  const decide = useCallback(
    async (assistantId: string, threadId: string, approved: boolean, comment: string) => {
      if (busy) return;
      const controller = new AbortController();
      activeRequest.current = controller;
      setBusy(true);
      updateAssistant(assistantId, (turn) => ({
        ...turn,
        streaming: true,
        approvalDecision: approved ? 'approved' : 'rejected',
      }));
      try {
        await resumeAgentStream(
          threadId,
          approved,
          comment,
          accessToken,
          (event) => consumeEvent(assistantId, event),
          controller.signal,
        );
      } catch (error) {
        const msg = error instanceof Error ? error.message : '审批恢复失败';
        updateAssistant(assistantId, (turn) => ({ ...turn, streaming: false, error: msg }));
      } finally {
        activeRequest.current = null;
        setBusy(false);
      }
    },
    [accessToken, busy, consumeEvent, updateAssistant],
  );

  const uploadReport = useCallback(async (file: File) => {
    if (busy) return;
    if (!currentSessionIdRef.current) {
      const session = createSession([]);
      saveSession(session);
      queueRemoteSave(session);
      currentSessionIdRef.current = session.id;
      setCurrentSessionId(session.id);
      setSessions(loadSessions());
    }
    const userId = crypto.randomUUID();
    const assistantId = crypto.randomUUID();
    const pending: ConversationTurn[] = [
      ...turns,
      {
        id: userId,
        role: 'user',
        content: `上传检查报告：${file.name}`,
        reasoning: [],
        streaming: false,
        attachment: {
          name: file.name,
          size: file.size,
          mediaType: file.type || 'application/octet-stream',
          status: 'uploading',
        },
      },
      {
        id: assistantId,
        role: 'assistant',
        content: '',
        reasoning: ['正在安全读取报告内容', '正在提取检查项目与原文异常标记'],
        streaming: true,
      },
    ];
    setTurns(pending);
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    try {
      const result = await analyzeMedicalReport(file, accessToken, controller.signal);
      updateAssistant(assistantId, (turn) => ({
        ...turn,
        content: formatReportAnalysis(result),
        streaming: false,
        status: 'completed',
      }));
      setTurns((current) => {
        const updated = current.map((turn) => turn.id === userId && turn.attachment
          ? { ...turn, attachment: { ...turn.attachment, status: 'analyzed' as const } }
          : turn);
        persistTurns(updated);
        return updated;
      });
    } catch (error) {
      if (!controller.signal.aborted) {
        const message = error instanceof Error ? error.message : '报告分析失败';
        updateAssistant(assistantId, (turn) => ({ ...turn, streaming: false, error: message }));
        setTurns((current) => {
          const updated = current.map((turn) => turn.id === userId && turn.attachment
            ? { ...turn, attachment: { ...turn.attachment, status: 'failed' as const } }
            : turn);
          persistTurns(updated);
          return updated;
        });
      }
    } finally {
      activeRequest.current = null;
      setBusy(false);
    }
  }, [accessToken, busy, persistTurns, queueRemoteSave, turns, updateAssistant]);

  const cancel = useCallback(() => activeRequest.current?.abort(), []);

  const switchSession = useCallback(
    (sessionId: string) => {
      if (busy) return;
      const session = loadSession(sessionId);
      if (session) {
        currentSessionIdRef.current = sessionId;
        setCurrentSessionId(sessionId);
        setTurns(session.turns);
      }
    },
    [busy],
  );

  const newSession = useCallback(() => {
    if (busy) return;
    const session = createSession([]);
    saveSession(session);
    queueRemoteSave(session);
    currentSessionIdRef.current = session.id;
    setCurrentSessionId(session.id);
    setTurns([]);
    setSessions(loadSessions());
  }, [busy, queueRemoteSave]);

  const deleteSession = useCallback(
    (sessionId: string) => {
      if (busy) return;
      deleteStoredSession(sessionId);
      void deleteRemoteSession(accessToken, sessionId).catch(() => undefined);
      const updated = loadSessions();
      setSessions(updated);
      if (currentSessionIdRef.current === sessionId) {
        const nextSession = updated[0];
        if (nextSession) {
          currentSessionIdRef.current = nextSession.id;
          setCurrentSessionId(nextSession.id);
          setTurns(nextSession.turns);
        } else {
          currentSessionIdRef.current = null;
          setCurrentSessionId(null);
          setTurns([]);
        }
      }
    },
    [accessToken, busy],
  );

  const clear = useCallback(() => {
    if (!busy) newSession();
  }, [busy, newSession]);

  const updateSession = useCallback((
    sessionId: string,
    patch: { title?: string; favorite?: boolean; archived?: boolean },
  ) => {
    patchSession(sessionId, patch);
    const updated = loadSession(sessionId);
    if (updated) queueRemoteSave(updated);
    setSessions(loadSessions());
  }, [queueRemoteSave]);

  return {
    turns,
    busy,
    sessions,
    currentSessionId,
    send,
    uploadReport,
    decide,
    cancel,
    clear,
    switchSession,
    newSession,
    deleteSession,
    updateSession,
  };
}

function formatReportAnalysis(report: ReportAnalysis): string {
  const flagLabel = {
    high: '↑ 偏高',
    low: '↓ 偏低',
    abnormal: '异常',
    unknown: '未标记',
  } as const;
  const safeFileName = report.fileName.replace(/[|`<>]/g, '_');
  const sections = [`## 检查报告解读\n\n**文件：** ${safeFileName}\n\n${report.summary}`];
  if (report.isSynthetic) {
    sections.push(
      '### 演示数据提示\n\n这是一份合成演示报告，所有身份信息和检验数值仅用于软件功能测试，不可用于诊疗。',
    );
  }
  const contextRows = [
    ['检查/采样时间', report.patientContext.collectedAt],
    ['报告时间', report.patientContext.reportedAt],
    ['年龄', report.patientContext.age == null ? null : `${report.patientContext.age} 岁`],
    ['性别', report.patientContext.sex],
    ['妊娠/哺乳', report.patientContext.pregnancyStatus],
    ['就诊原因', report.patientContext.visitReason],
    ['主要不适', report.patientContext.symptoms],
    ['既往疾病', report.patientContext.medicalHistory],
    ['当前用药', report.patientContext.currentMedications],
  ].filter((row): row is [string, string] => typeof row[1] === 'string' && Boolean(row[1]));
  if (contextRows.length > 0) {
    sections.push(
      `### 报告中已识别的信息\n\n${contextRows.map(([label, value]) => `- **${label}：** ${value}`).join('\n')}`,
    );
  }
  if (report.findings.length > 0) {
    const rows = report.findings.map((finding) =>
      `| ${finding.item} | ${finding.result} | ${finding.reference || '报告未提供'} | ${flagLabel[finding.flag]} |`,
    );
    sections.push(
      `### 报告原文项目\n\n| 项目 | 结果 | 参考范围 | 原文标记 |\n|---|---:|---:|---|\n${rows.join('\n')}`,
    );
  }
  if (report.patientContext.urgentInstruction) {
    sections.push(`### 报告原文中的就医提示\n\n- ${report.patientContext.urgentInstruction}`);
  }
  if (report.followUpQuestions.length > 0) {
    sections.push(`### 为了进一步判断，请补充\n\n${report.followUpQuestions.map((item) => `- ${item}`).join('\n')}`);
  }
  sections.push(`### 安全边界\n\n${report.warnings.map((item) => `- ${item}`).join('\n')}`);
  return sections.join('\n\n');
}
