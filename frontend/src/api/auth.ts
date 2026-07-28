const COMPACT_JWT = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;
const MAX_JWT_LENGTH = 8_192;

export function normalizeAccessToken(value: string): string {
  let token = value.trim();
  if (/^Bearer\s+/i.test(token)) token = token.replace(/^Bearer\s+/i, '').trim();

  if (!token || token.length > MAX_JWT_LENGTH || !COMPACT_JWT.test(token)) {
    throw new Error('JWT 格式无效：请仅粘贴 data.accessToken，可带或不带 Bearer 前缀');
  }
  return token;
}
