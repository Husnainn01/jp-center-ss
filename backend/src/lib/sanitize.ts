/**
 * Input sanitization utilities.
 * Strips HTML tags, trims, and enforces max length.
 */

const HTML_TAG_RE = /<[^>]*>/g;

/** Strip HTML tags and trim whitespace. */
export function sanitize(input: unknown, maxLength = 500): string {
  if (input == null) return "";
  const str = String(input).trim();
  return str.replace(HTML_TAG_RE, "").slice(0, maxLength);
}

/** Validate an integer ID from request params or body. Returns NaN if invalid. */
export function safeInt(input: unknown): number {
  const n = parseInt(String(input));
  if (isNaN(n) || n < 0 || n > 2147483647) return NaN;
  return n;
}

/** Validate email format (basic). */
export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 255;
}
