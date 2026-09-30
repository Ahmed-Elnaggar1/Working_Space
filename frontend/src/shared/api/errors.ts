import type { BackendErrorPayload } from './types';

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly requestId?: string;
  public readonly details?: unknown;

  constructor(status: number, code: string, message: string, requestId?: string, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;

    // Maintains proper stack trace in V8 environments
    const errorConstructor = Error as unknown as {
      captureStackTrace?: (targetObject: object, constructorOpt?: unknown) => void;
    };
    if (typeof errorConstructor.captureStackTrace === 'function') {
      errorConstructor.captureStackTrace(this, ApiError);
    }
  }
}

export async function parseApiError(response: Response): Promise<ApiError> {
  const status = response.status;

  try {
    const data = (await response.json()) as BackendErrorPayload;
    if (data?.error) {
      return new ApiError(
        status,
        data.error.code || `HTTP_${status}`,
        data.error.message || response.statusText || `Request failed with status ${status}`,
        data.error.request_id,
        data.error.details
      );
    }
  } catch {
    // Response body is not valid JSON (e.g. 502 Bad Gateway or raw text)
  }

  return new ApiError(
    status,
    `HTTP_${status}`,
    response.statusText || `Request failed with status ${status}`
  );
}
