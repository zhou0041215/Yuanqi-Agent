import type { AgentStreamEvent, AgentUiData, JsonValue } from './types';

const MAX_BUFFER_LENGTH = 1_000_000;

export interface RawSseEvent {
  event: string;
  data: string;
  id?: string;
}

export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<RawSseEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      if (buffer.length > MAX_BUFFER_LENGTH) {
        throw new Error('SSE 缓冲区超过安全上限');
      }
      const extracted = extractFrames(buffer);
      buffer = extracted.rest;
      for (const frame of extracted.frames) {
        const event = parseFrame(frame);
        if (event) yield event;
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      const event = parseFrame(buffer);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}

export function decodeAgentEvent(raw: RawSseEvent): AgentStreamEvent {
  let payload: unknown;
  try {
    payload = JSON.parse(raw.data);
  } catch {
    throw new Error(`SSE 事件 ${raw.event} 包含无效 JSON`);
  }
  if (!isRecord(payload)) throw new Error(`SSE 事件 ${raw.event} 结构无效`);

  switch (raw.event) {
    case 'reasoning':
      return { type: 'reasoning', reasoning: requiredString(payload.reasoning, 'reasoning') };
    case 'text':
      return { type: 'text', text: requiredString(payload.text, 'text', true) };
    case 'uiData':
      if (!isRecord(payload.uiData)) throw new Error('uiData 结构无效');
      return { type: 'uiData', uiData: validateUiData(payload.uiData) };
    case 'done':
      return {
        type: 'done',
        threadId: requiredString(payload.threadId, 'threadId'),
        status: requiredString(payload.status, 'status'),
      };
    case 'tool_result':
      if (!isRecord(payload.toolResult)) throw new Error('toolResult 结构无效');
      return {
        type: 'tool_result',
        toolResult: {
          toolName: requiredString(payload.toolResult.toolName, 'toolResult.toolName'),
          result: payload.toolResult.result as JsonValue,
          formatted: requiredString(payload.toolResult.formatted, 'toolResult.formatted', true),
        },
      };
    case 'error':
      if (!isRecord(payload.error)) throw new Error('error 结构无效');
      return {
        type: 'error',
        error: {
          code: requiredString(payload.error.code, 'error.code'),
          message: requiredString(payload.error.message, 'error.message'),
          details: payload.error.details as never,
        },
      };
    default:
      throw new Error(`不支持的 SSE 事件类型：${raw.event}`);
  }
}

function extractFrames(buffer: string): { frames: string[]; rest: string } {
  const frames: string[] = [];
  let rest = buffer;
  while (true) {
    const boundary = /\r?\n\r?\n/.exec(rest);
    if (!boundary || boundary.index === undefined) break;
    frames.push(rest.slice(0, boundary.index));
    rest = rest.slice(boundary.index + boundary[0].length);
  }
  return { frames, rest };
}

function parseFrame(frame: string): RawSseEvent | null {
  let event = 'message';
  let id: string | undefined;
  const data: string[] = [];
  for (const line of frame.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue;
    const colon = line.indexOf(':');
    const field = colon >= 0 ? line.slice(0, colon) : line;
    let value = colon >= 0 ? line.slice(colon + 1) : '';
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value;
    if (field === 'data') data.push(value);
    if (field === 'id') id = value;
  }
  if (!data.length) return null;
  return { event, data: data.join('\n'), id };
}

function validateUiData(value: Record<string, unknown>): AgentUiData {
  if (value.type === 'approval_card') {
    if (!isRecord(value.targetParameters)) throw new Error('审批参数结构无效');
    const riskLevel = requiredString(value.riskLevel, 'riskLevel');
    if (!['low', 'medium', 'high', 'critical'].includes(riskLevel)) {
      throw new Error('审批风险等级无效');
    }
    return {
      type: 'approval_card',
      threadId: requiredString(value.threadId, 'threadId'),
      action: requiredString(value.action, 'action'),
      riskLevel: riskLevel as 'low' | 'medium' | 'high' | 'critical',
      tool: requiredString(value.tool, 'tool'),
      targetParameters: value.targetParameters as never,
      fingerprint: requiredString(value.fingerprint, 'fingerprint'),
    };
  }
  if (value.type === 'chart') {
    return value as unknown as AgentUiData;
  }
  throw new Error('不支持的动态组件类型');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function requiredString(value: unknown, field: string, allowEmpty = false): string {
  if (typeof value !== 'string' || (!allowEmpty && !value.trim())) {
    throw new Error(`${field} 必须是字符串`);
  }
  return value;
}
