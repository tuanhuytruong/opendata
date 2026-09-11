export type ApiFailure = Error & { status: number; code?: string; requestId?: string };

const boundedText = (value: string) => value.replace(/\s+/g, ' ').trim().slice(0, 500);

export async function parseApiResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') ?? '';
  const requestId = response.headers.get('x-request-id') ?? undefined;
  let payload: unknown = null;
  let fallback = '';

  if (contentType.includes('application/json')) {
    try {
      payload = await response.json();
    } catch {
      fallback = 'The server returned invalid JSON.';
    }
  } else {
    fallback = boundedText(await response.text());
  }

  if (response.ok) return payload as T;

  const body = payload as { detail?: unknown; message?: unknown; code?: unknown; request_id?: unknown } | null;
  const message = typeof body?.message === 'string'
    ? body.message
    : typeof body?.detail === 'string'
      ? body.detail
      : fallback || response.statusText || 'Request failed.';
  const error = new Error(`Request failed (${response.status}): ${message}`) as ApiFailure;
  error.status = response.status;
  error.code = typeof body?.code === 'string' ? body.code : undefined;
  error.requestId = typeof body?.request_id === 'string' ? body.request_id : requestId;
  throw error;
}
