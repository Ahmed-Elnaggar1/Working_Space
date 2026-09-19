import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { api, apiClient, setTokenProvider, getBaseUrl } from './client';
import { ApiError } from './errors';

describe('API Client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setTokenProvider(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('resolves base URL fallback correctly', () => {
    expect(getBaseUrl()).toBe('http://localhost:8000');
  });

  it('performs GET request and parses JSON response', async () => {
    const mockData = { id: '123', name: 'General' };
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const result = await api.get('/workspaces');
    expect(result).toEqual(mockData);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/workspaces',
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
      })
    );
  });

  it('appends query parameters to the URL', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 })
    );

    await api.get('/workspaces', { params: { limit: 10, search: 'test', empty: null } });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/workspaces?limit=10&search=test',
      expect.anything()
    );
  });

  it('attaches Authorization header when token provider is set', async () => {
    setTokenProvider(() => 'my-secret-jwt-token');

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 })
    );

    await api.get('/auth/me');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/me',
      expect.objectContaining({
        headers: expect.any(Headers),
      })
    );

    const callHeaders = (vi.mocked(globalThis.fetch).mock.calls[0][1]?.headers) as Headers;
    expect(callHeaders.get('Authorization')).toBe('Bearer my-secret-jwt-token');
  });

  it('omits Authorization header when token is null', async () => {
    setTokenProvider(() => null);

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 })
    );

    await api.get('/health');

    const callHeaders = (vi.mocked(globalThis.fetch).mock.calls[0][1]?.headers) as Headers;
    expect(callHeaders.get('Authorization')).toBeNull();
  });

  it('serializes JSON body and sets Content-Type for POST requests', async () => {
    const payload = { email: 'user@example.com', password: 'password123' };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user: { id: 'u1' } }), { status: 201 })
    );

    await api.post('/auth/signup', payload);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/signup',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );

    const callHeaders = (vi.mocked(globalThis.fetch).mock.calls[0][1]?.headers) as Headers;
    expect(callHeaders.get('Content-Type')).toBe('application/json');
  });

  it('returns null for 204 No Content responses', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 })
    );

    const result = await api.post('/auth/logout');
    expect(result).toBeNull();
  });

  it('parses API.md standard error shape on 401/403/409/422 responses', async () => {
    const errorPayload = {
      error: {
        code: 'CONFLICT',
        message: 'A workspace with this name already exists.',
        request_id: 'req-12345',
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(errorPayload), {
        status: 409,
        statusText: 'Conflict',
        headers: { 'Content-Type': 'application/json' },
      })
    );

    try {
      await api.post('/workspaces', { name: 'Engineering' });
      expect.unreachable('Should have thrown an ApiError');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiError = err as ApiError;
      expect(apiError.status).toBe(409);
      expect(apiError.code).toBe('CONFLICT');
      expect(apiError.message).toBe('A workspace with this name already exists.');
      expect(apiError.requestId).toBe('req-12345');
    }
  });

  it('parses validation error details on 422 Unprocessable Entity', async () => {
    const errorPayload = {
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Validation failed',
        request_id: 'req-999',
        details: [{ loc: ['body', 'email'], msg: 'value is not a valid email address' }],
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(errorPayload), { status: 422 })
    );

    await expect(api.post('/auth/signup', { email: 'invalid' })).rejects.toMatchObject({
      status: 422,
      code: 'VALIDATION_ERROR',
      message: 'Validation failed',
      requestId: 'req-999',
      details: errorPayload.error.details,
    });
  });

  it('falls back gracefully on non-JSON error responses (e.g. 502 Bad Gateway)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response('<html><body>Bad Gateway</body></html>', {
        status: 502,
        statusText: 'Bad Gateway',
      })
    );

    await expect(api.get('/health')).rejects.toMatchObject({
      status: 502,
      code: 'HTTP_502',
      message: 'Bad Gateway',
    });
  });

  it('wraps network disconnects into ApiError with NETWORK_ERROR code', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    await expect(apiClient('/health')).rejects.toMatchObject({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Failed to fetch',
    });
  });
});
