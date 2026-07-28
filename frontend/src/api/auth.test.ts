import { describe, expect, it } from 'vitest';

import { normalizeAccessToken } from './auth';

describe('normalizeAccessToken', () => {
  it('accepts a compact JWT and removes an optional Bearer prefix', () => {
    expect(normalizeAccessToken(' Bearer header.payload.signature ')).toBe(
      'header.payload.signature',
    );
  });

  it('rejects a complete API response or other non-JWT text', () => {
    expect(() => normalizeAccessToken('{"message":"成功","data":{}}')).toThrow(
      'JWT 格式无效',
    );
  });
});
