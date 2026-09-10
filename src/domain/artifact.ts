import { ChartRequest, ChartResult } from '../types';
import { scopedChartRequest, scopeKey } from './workspaceScope';

export interface ExecutedChartArtifact {
  artifactId: string;
  request: ChartRequest;
  requestKey: string;
  result: ChartResult;
}

/** Only a server result whose validated request matches may enable downstream actions. */
export function executedChartArtifact(artifactId: string, runId: string, requested: ChartRequest, result: ChartResult): ExecutedChartArtifact | null {
  if (!result.request) return null;
  const request = scopedChartRequest(requested, requested.date_scope);
  const executed = scopedChartRequest(result.request, result.request.date_scope);
  const requestKey = JSON.stringify({ request, scope: scopeKey(runId, request.date_scope) });
  const executedKey = JSON.stringify({ request: executed, scope: scopeKey(runId, executed.date_scope) });
  if (requestKey !== executedKey) return null;
  return { artifactId, request: executed, requestKey: executedKey, result };
}
