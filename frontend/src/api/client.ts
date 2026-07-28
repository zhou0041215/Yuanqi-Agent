import { decodeAgentEvent, parseSseStream } from './sse';
import type { AgentRunBody, AgentStreamEvent, ReportAnalysis } from './types';
import { normalizeAccessToken } from './auth';

type EventHandler = (event: AgentStreamEvent) => void;

const configuredBase = window.__YUANQI_CONFIG__?.agentApiBaseUrl ?? import.meta.env.VITE_AGENT_API_BASE_URL;
const apiBase = (configuredBase || '').replace(/\/$/, '');

export async function startAgentStream(
  body: AgentRunBody,
  accessToken: string,
  onEvent: EventHandler,
  signal?: AbortSignal,
): Promise<void> {
  return streamRequest('/api/v1/agent/stream', body, accessToken, onEvent, signal);
}

export async function resumeAgentStream(
  threadId: string,
  approved: boolean,
  comment: string,
  accessToken: string,
  onEvent: EventHandler,
  signal?: AbortSignal,
): Promise<void> {
  return streamRequest(
    `/api/v1/agent/threads/${encodeURIComponent(threadId)}/resume/stream`,
    { approved, comment: comment || undefined },
    accessToken,
    onEvent,
    signal,
  );
}

export async function analyzeMedicalReport(
  file: File,
  accessToken: string,
  signal?: AbortSignal,
): Promise<ReportAnalysis> {
  const body = new FormData();
  body.append('file', file);
  const response = await fetch(`${apiBase}/api/v1/medical-reports/analyze`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${normalizeAccessToken(accessToken)}`,
      Accept: 'application/json',
      'X-Trace-Id': crypto.randomUUID(),
    },
    body,
    signal,
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<ReportAnalysis>;
}

async function streamRequest(
  path: string,
  body: unknown,
  accessToken: string,
  onEvent: EventHandler,
  signal?: AbortSignal,
): Promise<void> {
  const normalizedToken = normalizeAccessToken(accessToken);
  const response = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${normalizedToken}`,
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      'X-Trace-Id': crypto.randomUUID(),
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const message = await readError(response);
    throw new Error(message);
  }
  if (!response.body) throw new Error('响应不包含可读取的数据流');

  for await (const raw of parseSseStream(response.body)) {
    onEvent(decodeAgentEvent(raw));
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { message?: unknown };
    if (typeof payload.message === 'string') return payload.message;
  } catch {
    // Fall back to a status-based message when the gateway did not return JSON.
  }
  return `请求失败（HTTP ${response.status}）`;
}
