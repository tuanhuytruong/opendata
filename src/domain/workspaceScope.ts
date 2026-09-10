import { ChartRequest, DateScope } from '../types';

/** Canonical serialized scope for every request originating in the workspace. */
export function normalizeDateScope(scope?: DateScope | null): DateScope | undefined {
  if (!scope?.column) return undefined;
  return {
    column: scope.column,
    ...(scope.start ? { start: scope.start } : {}),
    ...(scope.end ? { end: scope.end } : {}),
  };
}

export function scopeKey(runId: string, scope?: DateScope | null): string {
  return JSON.stringify({ runId, dateScope: normalizeDateScope(scope) ?? null });
}

export function scopedChartRequest(request: ChartRequest, scope?: DateScope | null): ChartRequest {
  return { ...request, date_scope: normalizeDateScope(scope) };
}
