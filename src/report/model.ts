import type { ChartRequest, ChartResult, ReportLayoutTemplate } from '../types';

export type ReportPageSettings = { width: 'desktop'; columns: 12; row_height: number; gap: number };
export type ReportPage = { page_id: string; title: string; order: number };
export type ReportPlacement = { block_id: string; page_id: string; x: number; y: number; w: number; h: number };
export type ReportArtifactSnapshot = {
  artifact_id: string;
  origin: 'executive_hub' | 'data_copilot' | 'legacy' | 'unknown';
  chart: ChartRequest;
  result?: ChartResult | null;
  provenance: Record<string, unknown>;
  created_at: string;
  artifact_hash: string;
};
export type ReportBlock =
  | { type: 'header'; block_id: string; text: string; level: 1 | 2 | 3 }
  | { type: 'text'; block_id: string; text: string }
  | { type: 'note'; block_id: string; text: string; tone: 'neutral' | 'info' | 'warning' | 'success' }
  | { type: 'divider'; block_id: string }
  | { type: 'kpi_strip'; block_id: string; artifact_ids: string[] }
  | { type: 'action_table'; block_id: string; rows: Array<Record<string, string>> }
  | { type: 'chart'; block_id: string; artifact_id: string; view: 'chart'; title: string }
  | { type: 'data_table'; block_id: string; artifact_id: string; view: 'table'; title: string }
  | { type: 'glossary'; block_id: string; artifact_ids: string[]; manual_note_ids: string[] };
export type ReportDocumentV2 = {
  schema_version: 2;
  run_id: string;
  title: string;
  locale: 'en' | 'vi';
  page_settings: ReportPageSettings;
  pages: ReportPage[];
  blocks: ReportBlock[];
  placements: ReportPlacement[];
  artifact_library: ReportArtifactSnapshot[];
  updated_at: string;
  revision: number;
};

export const emptyReportV2 = (runId: string): ReportDocumentV2 => ({
  schema_version: 2,
  run_id: runId,
  title: 'Custom Report',
  locale: 'en',
  page_settings: { width: 'desktop', columns: 12, row_height: 24, gap: 16 },
  pages: [{ page_id: 'page-1', title: 'Page 1', order: 0 }],
  blocks: [], placements: [], artifact_library: [], updated_at: '', revision: 0,
});

export const blockFor = (document: ReportDocumentV2, blockId: string) => document.blocks.find(block => block.block_id === blockId);
export const placementFor = (document: ReportDocumentV2, blockId: string) => document.placements.find(item => item.block_id === blockId);
export const artifactFor = (document: ReportDocumentV2, artifactId: string) => document.artifact_library.find(item => item.artifact_id === artifactId);
export const isTemplate = (value: string | undefined): value is ReportLayoutTemplate => ['executive_briefing', 'sales_performance_review', 'category_division_deep_dive', 'weekly_monthly_business_review'].includes(value ?? '');
