/**
 * Vigil API Dispatcher
 * Selects between realApi and mockApi based on NEXT_PUBLIC_API_MODE env variable.
 * Enforces production build assertion to prevent mock mode deployment.
 */

import { realApi, idempotencyKey, decodeTokenPayload } from './api.real';
import { mockApi } from './api.mock';

const API_MODE = process.env.NEXT_PUBLIC_API_MODE || 'real';

// Production safety assertion: throw startup error if mock mode is attempted in production
if (process.env.NODE_ENV === 'production' && API_MODE === 'mock') {
  throw new Error('FATAL: NEXT_PUBLIC_API_MODE=mock is strictly forbidden in production builds.');
}

export const api = API_MODE === 'mock' ? mockApi : realApi;

export { idempotencyKey, decodeTokenPayload };
