import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Copy, Download, GripVertical, LayoutTemplate, Plus, Redo2, Save, Trash2, Undo2 } from 'lucide-react';
import GridLayout, { Layout } from 'react-grid-layout';
import type { Language } from '../i18n';
import type { CustomReportDocument } from '../types';
import { applyTemplateV2, chartSnapshot, createReportExport, getReportV2, saveReportV2 } from './api';
import { artifactFor, blockFor, emptyReportV2, placementFor, type ReportBlock, type ReportDocumentV2 } from './model';
import ValidatedChart from '../components/ValidatedChart';

type Props = { runId: string; report: CustomReportDocument | null; language: Language; onChange: (next: CustomReportDocument) => void };
type SaveState = 'clean' | 'dirty' | 'saving' | 'saved' | 'error' | 'conflict';

const templates = [
  ['executive_briefing', 'Executive Briefing', 'Cover → KPI → synthesis → drivers → actions'],
  ['sales_performance_review', 'Sales Performance Review', 'Asymmetric trend → drivers → evidence table'],
  ['category_division_deep_dive', 'Category / Division Deep Dive', 'Scope → segment ranking → comparison → glossary'],
  ['weekly_monthly_business_review', 'Weekly / Monthly Business Review', 'Period snapshot → trends → decisions → owners'],
] as const;
const safeId = (prefix: string) => `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
const defaultGeometry = (type: ReportBlock['type'], index: number) => type === 'chart' ? { x: 0, y: index * 8, w: 8, h: 8 } : type === 'data_table' ? { x: 0, y: index * 8, w: 12, h: 8 } : { x: 0, y: index * 5, w: 12, h: 4 };
const blockTitle = (block: ReportBlock) => block.type === 'header' || block.type === 'text' || block.type === 'note' ? block.text : block.type.replace('_', ' ');

export default function ReportBuilder({ runId, report, language, onChange }: Props) {
  const [document, setDocument] = useState<ReportDocumentV2>(() => emptyReportV2(runId));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pageId, setPageId] = useState('page-1');
  const [state, setState] = useState<SaveState>('clean');
  const [message, setMessage] = useState('');
  const [preview, setPreview] = useState(false);
  const [history, setHistory] = useState<ReportDocumentV2[]>([]);
  const [future, setFuture] = useState<ReportDocumentV2[]>([]);
  const initial = useRef(true);
  const pending = useRef<ReportDocumentV2 | null>(null);
  const loaded = useRef(false);
  const documentRef = useRef(document);
  const persistedRevision = useRef(document.revision);
  const saveQueue = useRef(Promise.resolve());
  const canvasAreaRef = useRef<HTMLDivElement>(null);
  const [canvasWidth, setCanvasWidth] = useState(760);

  useEffect(() => {
    const element = canvasAreaRef.current;
    if (!element) return;
    const updateWidth = () => setCanvasWidth(Math.max(1, Math.floor(element.clientWidth - 32)));
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let active = true;
    void getReportV2(runId).then(next => { if (active) { documentRef.current = next; persistedRevision.current = next.revision; setDocument(next); setPageId(next.pages[0]?.page_id ?? 'page-1'); loaded.current = true; } }).catch(error => { if (active) setMessage(error instanceof Error ? error.message : 'Unable to load the report builder.'); });
    return () => { active = false; };
  }, [runId]);


  const commit = useCallback((next: ReportDocumentV2, dirty = true) => {
    setHistory(previous => [...previous.slice(-29), documentRef.current]);
    setFuture([]);
    documentRef.current = next;
    setDocument(next);
    if (dirty && loaded.current) setState('dirty');
  }, []);
  const currentPage = document.pages.find(page => page.page_id === pageId) ?? document.pages[0];
  const pageBlocks = useMemo(() => document.blocks.filter(block => document.placements.some(item => item.page_id === currentPage?.page_id && item.block_id === block.block_id)), [document, currentPage?.page_id]);
  const selected = selectedId ? blockFor(document, selectedId) : undefined;

  const persist = useCallback((next: ReportDocumentV2) => {
    setState('saving'); setMessage(''); pending.current = next;
    saveQueue.current = saveQueue.current.then(async () => {
      try {
        const queued = { ...next, revision: persistedRevision.current };
        const saved = await saveReportV2(runId, queued);
        documentRef.current = saved;
        persistedRevision.current = saved.revision;
        setDocument(current => current.revision <= saved.revision ? saved : current);
        if (pending.current === next) { setState('saved'); setMessage('Saved'); }
      } catch (error) {
        if (pending.current === next) { setState(error instanceof Error && error.message.includes('(409)') ? 'conflict' : 'error'); setMessage(error instanceof Error ? error.message : 'Unable to save report.'); }
      }
    });
  }, [runId]);

  const persistLatest = useCallback(() => persist(documentRef.current), [persist]);

  const mutate = (updater: (current: ReportDocumentV2) => ReportDocumentV2, save = true) => {
    const next = updater(document);
    commit(next);
    if (save) persist(next);
  };
  const saveDraft = () => persistLatest();
  const addBlock = (type: ReportBlock['type'], artifactId?: string, view: 'chart' | 'table' = 'chart') => {
    const blockId = safeId(type);
    const index = document.blocks.length;
    let block: ReportBlock;
    if (type === 'header') block = { type, block_id: blockId, text: 'New section', level: 2 };
    else if (type === 'text') block = { type, block_id: blockId, text: 'Add evidence-grounded commentary.' };
    else if (type === 'note') block = { type, block_id: blockId, text: 'Add a note or watchout.', tone: 'info' };
    else if (type === 'divider') block = { type, block_id: blockId };
    else if (type === 'kpi_strip') block = { type, block_id: blockId, artifact_ids: artifactId ? [artifactId] : [] };
    else if (type === 'action_table') block = { type, block_id: blockId, rows: [] };
    else if (type === 'glossary') block = { type, block_id: blockId, artifact_ids: document.artifact_library.map(item => item.artifact_id), manual_note_ids: [] };
    else if (artifactId && type === 'chart') block = { type: 'chart', block_id: blockId, artifact_id: artifactId, view: 'chart', title: '' };
    else if (artifactId && type === 'data_table') block = { type: 'data_table', block_id: blockId, artifact_id: artifactId, view: 'table', title: '' };
    else return;
    const geometry = defaultGeometry(type, index);
    mutate(current => ({ ...current, blocks: [...current.blocks, block], placements: [...current.placements, { block_id: blockId, page_id: currentPage?.page_id ?? 'page-1', ...geometry }] }));
    setSelectedId(blockId);
  };
  const removeSelected = () => { if (!selectedId) return; mutate(current => ({ ...current, blocks: current.blocks.filter(block => block.block_id !== selectedId), placements: current.placements.filter(item => item.block_id !== selectedId) })); setSelectedId(null); };
  const duplicateSelected = () => { if (!selected) return; const blockId = safeId(selected.type); const placement = placementFor(document, selected.block_id); mutate(current => ({ ...current, blocks: [...current.blocks, { ...selected, block_id: blockId } as ReportBlock], placements: [...current.placements, { ...(placement ?? { page_id: currentPage?.page_id ?? 'page-1', x: 0, y: 0, w: 6, h: 4 }), block_id: blockId, y: (placement?.y ?? 0) + (placement?.h ?? 4) }] })); setSelectedId(blockId); };
  const addPage = () => { const nextPage = { page_id: safeId('page'), title: `Page ${document.pages.length + 1}`, order: document.pages.length }; mutate(current => ({ ...current, pages: [...current.pages, nextPage] })); setPageId(nextPage.page_id); };
  const changeLayout = (layout: Layout[]) => {
    const next = { ...document, placements: document.placements.map(item => {
      const changed = layout.find(entry => entry.i === item.block_id);
      return changed ? { ...item, x: changed.x, y: changed.y, w: changed.w, h: changed.h } : item;
    }) };
    commit(next);
    persist(next);
  };
  const updateSelectedText = (value: string) => { if (!selected) return; mutate(current => ({ ...current, blocks: current.blocks.map(block => block.block_id === selected.block_id && ('text' in block) ? { ...block, text: value } as ReportBlock : block) }), false); };
  const undo = () => { const previous = history.at(-1); if (!previous) return; setFuture(items => [...items, documentRef.current]); setHistory(items => items.slice(0, -1)); documentRef.current = previous; setDocument(previous); setState('dirty'); };
  const redo = () => { const next = future.at(-1); if (!next) return; setHistory(items => [...items, documentRef.current]); setFuture(items => items.slice(0, -1)); documentRef.current = next; setDocument(next); setState('dirty'); };
  const applyTemplate = async (template: string) => {
    if (!window.confirm('Replace canvas layout and keep Library?')) return;
    setState('saving'); setMessage('');
    saveQueue.current = saveQueue.current.then(async () => {
      try {
        const next = await applyTemplateV2(runId, persistedRevision.current, template);
        documentRef.current = next;
        persistedRevision.current = next.revision;
        setDocument(next);
        setPageId(next.pages[0]?.page_id ?? 'page-1');
        setState('saved'); setMessage('Saved');
      } catch (error) {
        setState(error instanceof Error && error.message.includes('(409)') ? 'conflict' : 'error');
        setMessage(error instanceof Error ? error.message : 'Unable to apply template.');
      }
    });
  };
  const exportReport = async () => { setState('saving'); try { const result = await createReportExport(runId, documentRef.current.revision); window.open(`/api/runs/${runId}/custom-report/exports/${result.export_id}`, '_blank', 'noopener,noreferrer'); setState('saved'); setMessage(`Exported revision ${result.revision}`); } catch (error) { setState('error'); setMessage(error instanceof Error ? error.message : 'Unable to export this report.'); } };
  const addLibraryArtifact = async (artifactId: string, view: 'chart' | 'table') => { const item = artifactFor(document, artifactId); if (!item) return; addBlock(view === 'table' ? 'data_table' : 'chart', item.artifact_id, view); };
  const statusLabel = state === 'dirty' ? 'Unsaved changes' : state === 'saving' ? 'Saving…' : state === 'conflict' ? 'Conflict — reload required' : message || (state === 'saved' ? 'Saved' : 'Ready');


  return <section className="report-builder" data-report-revision={document.revision}>
    <header className="report-builder-toolbar"><div><p className="section-eyebrow">Report Builder v2</p><input className="report-name-input" aria-label="Report name" value={document.title} onChange={event => mutate(current => ({ ...current, title: event.target.value }), false)} onBlur={saveDraft}/><span className={`report-save-state report-save-${state}`} aria-live="polite">{statusLabel}</span></div><div className="report-toolbar-actions"><button type="button" onClick={undo} disabled={!history.length} title="Undo"><Undo2 size={15}/></button><button type="button" onClick={redo} disabled={!future.length} title="Redo"><Redo2 size={15}/></button><button type="button" onClick={() => setPreview(value => !value)}>{preview ? 'Edit' : 'Preview'}</button><button type="button" onClick={saveDraft}><Save size={15}/>Save</button><button type="button" onClick={() => void exportReport()}><Download size={15}/>Export HTML</button></div></header>
    <div className="report-builder-shell">
      {!preview && <aside className="report-library" aria-label="Report Library"><div className="report-panel-heading"><div><p className="section-eyebrow">Reusable items</p><h2>Library</h2></div><button type="button" onClick={addPage} title="Add page"><Plus size={15}/></button></div><div className="library-group"><b>Blocks</b>{(['header', 'text', 'note', 'divider', 'kpi_strip', 'action_table', 'glossary'] as ReportBlock['type'][]).map(type => <button type="button" key={type} onClick={() => addBlock(type)}><Plus size={13}/>{type.replace('_', ' ')}</button>)}</div><div className="library-group"><b>Charts & tables</b>{document.artifact_library.map(item => <div className="library-artifact" key={item.artifact_id}><span><strong>{String(item.provenance.title || item.result?.title || item.artifact_id)}</strong><small>{item.origin} · {item.result?.request?.date_scope ? 'saved scope' : 'all data'}</small></span><button type="button" onClick={() => void addLibraryArtifact(item.artifact_id, 'chart')} aria-label={`Add ${item.artifact_id} chart`}><Plus size={13}/>Chart</button><button type="button" onClick={() => void addLibraryArtifact(item.artifact_id, 'table')} aria-label={`Add ${item.artifact_id} table`}>Table</button></div>)}</div><div className="library-group"><b>Templates</b>{templates.map(([id, title, description]) => <button type="button" className="template-choice" key={id} onClick={() => void applyTemplate(id)}><LayoutTemplate size={14}/><span><strong>{title}</strong><small>{description}</small></span></button>)}</div></aside>}
      <main ref={canvasAreaRef} className="report-canvas-area"><div className="report-page-tabs">{document.pages.map(page => <button type="button" key={page.page_id} className={page.page_id === currentPage?.page_id ? 'active' : ''} onClick={() => setPageId(page.page_id)}>{page.title}</button>)}</div><div className={`report-canvas ${preview ? 'report-canvas-preview' : ''}`}><GridLayout className="report-grid-layout" layout={pageBlocks.map(block => { const item = placementFor(document, block.block_id)!; return { i: block.block_id, x: item.x, y: item.y, w: item.w, h: item.h, minW: block.type === 'chart' ? 4 : 2, minH: block.type === 'chart' ? 6 : 2 }; })} cols={12} rowHeight={document.page_settings.row_height} width={canvasWidth} margin={[document.page_settings.gap, document.page_settings.gap]} isDraggable={!preview} isResizable={!preview} draggableHandle=".report-block-drag-handle" compactType={null} preventCollision={true} onLayoutChange={changeLayout}>{pageBlocks.map(block => <article key={block.block_id} className={`report-block report-block-${block.type} ${selectedId === block.block_id ? 'selected' : ''}`} onClick={() => setSelectedId(block.block_id)}><div className="report-block-handle report-block-drag-handle"><GripVertical size={14}/><span>{block.type.replace('_', ' ')}</span></div><BlockView block={block} document={document} language={language}/></article>)}</GridLayout>{!pageBlocks.length && <div className="report-empty-canvas"><Plus size={18}/><p>Add a block or validated artifact from Library.</p></div>}</div></main>
      {!preview && <aside className="report-inspector"><div className="report-panel-heading"><div><p className="section-eyebrow">Selected block</p><h2>Inspector</h2></div></div>{selected ? <><p className="inspector-type">{selected.type} · {selected.block_id}</p>{'text' in selected && <label>Content<textarea value={selected.text} onChange={event => updateSelectedText(event.target.value)} onBlur={saveDraft} rows={8}/></label>}{(selected.type === 'chart' || selected.type === 'data_table') && <p className="inspector-scope">Validated artifact: {selected.artifact_id}<br/>{artifactFor(document, selected.artifact_id)?.provenance.scope as string}</p>}<div className="inspector-actions"><button type="button" onClick={duplicateSelected}><Copy size={14}/>Duplicate</button><button type="button" onClick={removeSelected} className="danger"><Trash2 size={14}/>Delete</button></div></> : <p className="inspector-empty">Select a block on the canvas to edit, duplicate, or delete it.</p>}</aside>}
    </div>
  </section>;
}

function BlockView({ block, document, language }: { block: ReportBlock; document: ReportDocumentV2; language: Language }) {
  if (block.type === 'header') return <h2>{block.text}</h2>;
  if (block.type === 'text' || block.type === 'note') return <p>{block.text}</p>;
  if (block.type === 'divider') return <hr/>;
  if (block.type === 'action_table') return <div className="action-placeholder">Action tracker · add owner, action and deadline in Inspector</div>;
  if (block.type === 'glossary') return <div><h3>Glossary</h3><p>{block.artifact_ids.length} validated artifact definition{block.artifact_ids.length === 1 ? '' : 's'}</p></div>;
  if (block.type === 'kpi_strip') return <div className="kpi-strip-preview">{block.artifact_ids.map(id => <span key={id}>{artifactFor(document, id)?.result?.title ?? id}</span>)}</div>;
  const chart = chartSnapshot(document, block.artifact_id);
  if (!chart) return <div className="report-placeholder">Add a validated artifact from Library.</div>;
  return block.type === 'chart' ? <ValidatedChart result={chart} language={language} report/> : <div className="report-table-preview"><strong>{block.title || chart.title}</strong><table><thead><tr><th>Label</th><th>Value</th></tr></thead><tbody>{chart.rows.slice(0, 10).map((row, index) => <tr key={`${row.label}-${index}`}><td>{row.display_label ?? row.label}</td><td>{row.formatted_value ?? row.value}</td></tr>)}</tbody></table></div>;
}
