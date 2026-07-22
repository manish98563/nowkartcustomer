import * as Crypto from 'expo-crypto';

/**
 * Self-contained base64url encoding (no `btoa`/external base64 lib
 * dependency, so this works identically on iOS, Android, and web/Hermes).
 */
const BASE64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

function bytesToBase64(bytes: Uint8Array): string {
  let result = '';
  let i = 0;
  for (; i + 3 <= bytes.length; i += 3) {
    const chunk = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];
    result += BASE64_CHARS[(chunk >> 18) & 63];
    result += BASE64_CHARS[(chunk >> 12) & 63];
    result += BASE64_CHARS[(chunk >> 6) & 63];
    result += BASE64_CHARS[chunk & 63];
  }
  const remaining = bytes.length - i;
  if (remaining === 1) {
    const chunk = bytes[i] << 16;
    result += BASE64_CHARS[(chunk >> 18) & 63] + BASE64_CHARS[(chunk >> 12) & 63] + '==';
  } else if (remaining === 2) {
    const chunk = (bytes[i] << 16) | (bytes[i + 1] << 8);
    result +=
      BASE64_CHARS[(chunk >> 18) & 63] + BASE64_CHARS[(chunk >> 12) & 63] + BASE64_CHARS[(chunk >> 6) & 63] + '=';
  }
  return result;
}

function toBase64Url(base64: string): string {
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

/**
 * Generates a fresh PKCE (RFC 7636) verifier/challenge pair, entirely
 * on-device and held only in memory for the duration of a single sign-in
 * attempt — never persisted to disk. This matches Shopify's and RFC 8252's
 * native-app PKCE requirements exactly. Only the resulting `{code,
 * codeVerifier}` pair (never the verifier alone, never before a code
 * exists) is ever sent anywhere, and only once, to our own backend for the
 * actual token exchange — the device never calls Shopify's token endpoint
 * directly and never holds a real Shopify token.
 */
export async function generatePkcePair(): Promise<{ codeVerifier: string; codeChallenge: string }> {
  const randomBytes = await Crypto.getRandomBytesAsync(64);
  const codeVerifier = toBase64Url(bytesToBase64(randomBytes));

  const digestBase64 = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, codeVerifier, {
    encoding: Crypto.CryptoEncoding.BASE64,
  });
  const codeChallenge = toBase64Url(digestBase64);

  return { codeVerifier, codeChallenge };
}
