import { describe, expect, it } from 'vitest';

import { decodeAgentEvent, parseSseStream } from './sse';

function chunkedStream(source: string, sizes: number[]): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(source);
  let offset = 0;
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (offset >= bytes.length) {
        controller.close();
        return;
      }
      const size = sizes[index++ % sizes.length] ?? 1;
      controller.enqueue(bytes.slice(offset, offset + size));
      offset += size;
    },
  });
}

describe('parseSseStream', () => {
  it('reassembles fragmented UTF-8 and CRLF frames', async () => {
    const stream = chunkedStream(
      'event: reasoning\r\ndata: {"reasoning":"正在检索客户关系"}\r\n\r\n' +
        'event: text\ndata: {"text":"结论"}\n\n',
      [1, 2, 5, 3],
    );

    const events = [];
    for await (const event of parseSseStream(stream)) events.push(event);

    expect(events).toHaveLength(2);
    expect(decodeAgentEvent(events[0]!)).toEqual({
      type: 'reasoning',
      reasoning: '正在检索客户关系',
    });
    expect(decodeAgentEvent(events[1]!)).toEqual({ type: 'text', text: '结论' });
  });

  it('joins multiple data lines and ignores comments', async () => {
    const stream = chunkedStream(
      ': keep-alive\nevent: done\ndata: {"threadId":"thread-1",\ndata: "status":"completed"}\n\n',
      [7],
    );
    const events = [];
    for await (const event of parseSseStream(stream)) events.push(event);

    expect(decodeAgentEvent(events[0]!)).toEqual({
      type: 'done',
      threadId: 'thread-1',
      status: 'completed',
    });
  });

  it('rejects unknown dynamic UI instructions', () => {
    expect(() =>
      decodeAgentEvent({
        event: 'uiData',
        data: '{"uiData":{"type":"unsafe_widget"}}',
      }),
    ).toThrow('不支持的动态组件类型');
  });

  it.each(['uiData', 'approval'])(
    'decodes approval cards from the %s event',
    (event) => {
      expect(
        decodeAgentEvent({
          event,
          data: JSON.stringify({
            uiData: {
              type: 'approval_card',
              threadId: 'thread-2',
              action: '创建处方',
              riskLevel: 'critical',
              tool: 'create_prescription',
              targetParameters: { patient_id: 2 },
              fingerprint: 'fingerprint-2',
            },
          }),
        }),
      ).toEqual({
        type: 'uiData',
        uiData: {
          type: 'approval_card',
          threadId: 'thread-2',
          action: '创建处方',
          riskLevel: 'critical',
          tool: 'create_prescription',
          targetParameters: { patient_id: 2 },
          fingerprint: 'fingerprint-2',
        },
      });
    },
  );
});
