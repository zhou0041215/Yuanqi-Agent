import type { ConversationTurn } from '../hooks/useAgentConversation';

const STORAGE_KEY = 'yuanqi-sessions';
const MAX_SESSIONS = 50;

export interface StoredSession {
  id: string;
  title: string;
  turns: ConversationTurn[];
  createdAt: number;
  updatedAt: number;
  favorite?: boolean;
  archived?: boolean;
}

function generateTitle(turns: ConversationTurn[]): string {
  const firstUser = turns.find((t) => t.role === 'user');
  if (!firstUser) return '新会话';
  const text = firstUser.content.trim();
  return text.length > 30 ? text.slice(0, 30) + '…' : text;
}

export function saveSession(session: StoredSession): void {
  try {
    const sessions = loadSessions();
    const index = sessions.findIndex((s) => s.id === session.id);
    if (index >= 0) {
      sessions[index] = session;
    } else {
      sessions.unshift(session);
    }
    // Trim to max sessions
    const trimmed = sessions.slice(0, MAX_SESSIONS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    // localStorage might be full or unavailable
  }
}

export function loadSessions(): StoredSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as StoredSession[];
  } catch {
    return [];
  }
}

export function loadSession(id: string): StoredSession | null {
  const sessions = loadSessions();
  return sessions.find((s) => s.id === id) ?? null;
}

export function deleteSession(id: string): void {
  try {
    const sessions = loadSessions().filter((s) => s.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // ignore
  }
}

export function patchSession(id: string, patch: Partial<Pick<StoredSession, 'title' | 'favorite' | 'archived'>>): void {
  const sessions = loadSessions();
  const index = sessions.findIndex((session) => session.id === id);
  if (index < 0) return;
  const current = sessions[index];
  if (!current) return;
  sessions[index] = { ...current, ...patch, updatedAt: Date.now() };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

export function createSession(turns: ConversationTurn[]): StoredSession {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    title: generateTitle(turns),
    turns,
    createdAt: now,
    updatedAt: now,
  };
}

export function updateSessionTitle(session: StoredSession, turns: ConversationTurn[]): StoredSession {
  return {
    ...session,
    title: generateTitle(turns),
    turns,
    updatedAt: Date.now(),
  };
}

export async function loadRemoteSessions(accessToken: string): Promise<StoredSession[]> {
  const response = await fetch('/api/v1/conversations', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) throw new Error(`会话同步失败（HTTP ${response.status}）`);
  const envelope = await response.json() as { data: StoredSession[] };
  return Array.isArray(envelope.data) ? envelope.data : [];
}

export async function saveRemoteSession(
  accessToken: string,
  session: StoredSession,
): Promise<void> {
  const response = await fetch(`/api/v1/conversations/${encodeURIComponent(session.id)}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(session),
  });
  if (!response.ok) throw new Error(`会话保存失败（HTTP ${response.status}）`);
}

export async function deleteRemoteSession(accessToken: string, id: string): Promise<void> {
  const response = await fetch(`/api/v1/conversations/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok && response.status !== 404) {
    throw new Error(`会话删除失败（HTTP ${response.status}）`);
  }
}
