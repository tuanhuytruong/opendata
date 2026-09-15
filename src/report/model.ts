import type { ChartRequest, ChartResult, ReportLayoutTemplate } from '../types';

export type ReportPageSettings = { width: 'desktop'; columns: 12; row_height: number; gap: number };
export type RichTextMark = 'bold' | 'italic' | 'underline';
export type RichTextAlign = 'left' | 'center' | 'right';
export type RichTextSize = 'sm' | 'base' | 'lg' | 'xl';
export type RichTextInline = {
  type: 'text';
  text: string;
  marks?: Array<{ type: RichTextMark } | { type: 'fontSize'; attrs: { size: RichTextSize } }>;
};
export type RichTextNode =
  | { type: 'paragraph' | 'heading'; attrs?: { textAlign?: RichTextAlign; level?: 1 | 2 | 3 }; content?: RichTextInline[] }
  | { type: 'hardBreak' }
  | { type: 'bulletList' | 'orderedList' | 'listItem'; content?: RichTextNode[] };
export type RichTextDocument = { type: 'doc'; content: RichTextNode[] };
export type ReportChartPresentation = {
  title: string;
  chartType: string;
  orientation: 'horizontal' | 'vertical';
  metricLabel: string;
  dimensionLabel: string;
  rows: Array<{ label: string; displayLabel?: string; value: number; formattedValue: string; secondaryLabel?: string; secondaryValue?: number; secondaryFormattedValue?: string }>;
  requestedLimit: number;
  returnedCount: number;
  domain: [number, number];
  ticks: Array<{ value: number; label: string }>;
  paletteMode: 'single-series' | 'categorical' | 'grouped';
  locale: 'en' | 'vi';
};

export type ReportPage = { page_id: string; title: string; order: number };
export type ReportPlacement = { block_id: string; page_id: string; x: number; y: number; w: number; h: number };
export type ActionRow = { owner: string; action: string; deadline: string; status: 'not_started' | 'in_progress' | 'blocked' | 'done' };
export type GlossaryNote = { note_id: string; text: string };
export type ReportBlock =
  | { type: 'header'; block_id: string; text: string; rich_text?: RichTextDocument; level: 1 | 2 | 3 }
  | { type: 'text'; block_id: string; text: string; rich_text?: RichTextDocument }
  | { type: 'note'; block_id: string; text: string; rich_text?: RichTextDocument; tone: 'neutral' | 'info' | 'warning' | 'success' }
  | { type: 'divider'; block_id: string; style?: 'solid' | 'dashed' | 'dotted'; thickness?: 1 | 2 | 3; color?: 'slate' | 'indigo' | 'amber' }
  | { type: 'kpi_strip'; block_id: string; artifact_ids: string[]; items?: Array<{ artifact_id: string; row_label?: string; label_override?: string }> }
  | { type: 'action_table'; block_id: string; rows: ActionRow[] }
  | { type: 'glossary'; block_id: string; artifact_ids: string[]; manual_note_ids: string[]; authored_notes?: GlossaryNote[] }
  | { type: 'chart'; block_id: string; artifact_id: string; view: 'chart'; title: string }
  | { type: 'data_table'; block_id: string; artifact_id: string; view: 'table'; title: string; visible_rows?: number };
export type ReportArtifactSnapshot = {
  artifact_id: string;
  origin: 'executive_hub' | 'data_copilot' | 'legacy' | 'unknown';
  chart: ChartRequest;
  result?: ChartResult | null;
  presentation?: ReportChartPresentation;
  provenance: Record<string, unknown>;
  created_at: string;
  artifact_hash: string;
  dataset_sha256: string;
  view_capabilities: Array<'chart' | 'table'>;
};
export type ReportDocumentV2 = {
  schema_version: 2;
  run_id: string;
  title: string;
  locale: 'en' | 'vi';
  layout_blueprint: { template: ReportLayoutTemplate };
  page_settings: ReportPageSettings;
  pages: ReportPage[];
  blocks: ReportBlock[];
  placements: ReportPlacement[];
  artifact_library: ReportArtifactSnapshot[];
  updated_at: string;
  revision: number;
};

const emptyRichText = (text: string, level?: 1 | 2 | 3): RichTextDocument => ({
  type: 'doc',
  content: [{ type: level ? 'heading' : 'paragraph', ...(level ? { attrs: { level, textAlign: 'left' as const } } : {}), content: text ? [{ type: 'text', text }] : [] }],
});
export const emptyReportV2 = (runId: string): ReportDocumentV2 => ({
  schema_version: 2,
  run_id: runId,
  title: 'Custom Report',
  locale: 'en',
  layout_blueprint: { template: 'executive_briefing' },
  page_settings: { width: 'desktop', columns: 12, row_height: 24, gap: 16 },
  pages: [{ page_id: 'page-1', title: 'Page 1', order: 0 }],
  blocks: [],
  placements: [],
  artifact_library: [],
  updated_at: '',
  revision: 0,
});
export const blockFor = (document: ReportDocumentV2, blockId: string) => document.blocks.find(block => block.block_id === blockId);
export const placementFor = (document: ReportDocumentV2, blockId: string) => document.placements.find(item => item.block_id === blockId);
export const artifactFor = (document: ReportDocumentV2, artifactId: string) => document.artifact_library.find(item => item.artifact_id === artifactId);
export const chartSnapshot = (document: ReportDocumentV2, artifactId: string): ChartResult | null => artifactFor(document, artifactId)?.result ?? null;
export const richTextFor = (block: Extract<ReportBlock, { type: 'header' | 'text' | 'note' }>): RichTextDocument => block.rich_text ?? emptyRichText(block.text, block.type === 'header' ? block.level : undefined);
const plainTextFromNode = (node: RichTextNode): string => {
  const raw = node as unknown as { type: string; text?: string; content?: Array<RichTextNode | RichTextInline> };
  if (raw.type === 'hardBreak') return '\n';
  if (raw.type === 'text') return raw.text ?? '';
  return (raw.content ?? []).map(child => plainTextFromNode(child as RichTextNode)).join('');
};
export const withRichText = (block: Extract<ReportBlock, { type: 'header' | 'text' | 'note' }>, richText: RichTextDocument): ReportBlock => ({
  ...block,
  rich_text: richText,
  text: richText.content.map(plainTextFromNode).join('\n'),
});
