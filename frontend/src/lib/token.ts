/**
 * Token store — persists the JWT access token in sessionStorage.
 * sessionStorage is cleared when the tab closes (unlike localStorage),
 * reducing the window of token exposure.
 */
const TOKEN_KEY = 'vigil_access_token';

export function setToken(token: string): void {
  if (typeof window !== 'undefined') {
    sessionStorage.setItem(TOKEN_KEY, token);
  }
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  if (typeof window !== 'undefined') {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}
