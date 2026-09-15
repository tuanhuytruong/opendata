import { parseApiResponse } from '../api/response';
import type { ChartRequest, ChartResult } from '../types';
import type { ReportDocumentV2 } from './model';

const asChartResult = (value: Record<string, any> | undefined): ChartResult | null => value ? value as ChartResult : null;

const json = async <T>(response: Response) => parseApiResponse<T>(response);

export async function getReportV2(runId: string): Promise<ReportDocumentV2> {
  return json(await fetch(`/api/runs/${runId}/custom-report/v2`));
}

export async function saveReportV2(runId: string, document: ReportDocumentV2): Promise<ReportDocumentV2> {
  return json(await fetch(`/api/runs/${runId}/custom-report/v2`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_revision: document.revision, document: { ...document, revision: document.revision + 1 } }),
  }));
}

export async function addArtifactV2(runId: string, expectedRevision: number, artifactId: string, chart: ChartRequest, origin: 'executive_hub' | 'data_copilot' | 'unknown' = 'unknown', view: 'chart' | 'table' = 'chart'): Promise<ReportDocumentV2> {
  return json(await fetch(`/api/runs/${runId}/custom-report/v2/artifacts`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_revision: expectedRevision, artifact_id: artifactId, chart, origin, view }),
  }));
}

export async function deleteArtifactV2(runId: string, expectedRevision: number, artifactId: string): Promise<ReportDocumentV2> {
  return json(await fetch(`/api/runs/${runId}/custom-report/v2/artifacts/${encodeURIComponent(artifactId)}`, {
    method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_revision: expectedRevision }),
  }));
}

export async function applyTemplateV2(runId: string, expectedRevision: number, template: string): Promise<ReportDocumentV2> {
  return json(await fetch(`/api/runs/${runId}/custom-report/v2/templates/${encodeURIComponent(template)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_revision: expectedRevision, mode: 'replace_layout_keep_library' }),
  }));
}

export async function createReportExport(runId: string, revision: number): Promise<{ export_id: string; revision: number; format: 'html'; manifest: Record<string, unknown> }> {
  return json(await fetch(`/api/runs/${runId}/custom-report/exports`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ revision, format: 'html' }),
  }));
}

export const chartSnapshot = (document: ReportDocumentV2, artifactId: string): ChartResult | null => asChartResult(document.artifact_library.find(item => item.artifact_id === artifactId)?.result);
