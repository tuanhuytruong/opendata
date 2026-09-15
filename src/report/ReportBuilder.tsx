import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Copy, Download, GripVertical, LayoutTemplate, Plus, Redo2, Save, Trash2, Undo2 } from 'lucide-react';
import GridLayout, { Layout } from 'react-grid-layout';
import type { Language } from '../i18n';
import type { ChartResult } from '../types';
import { applyTemplateV2, createReportExport, getReportV2, saveReportV2 } from './api';
import { artifactFor, blockFor, emptyReportV2, placementFor, richTextFor, withRichText, type ReportBlock, type ReportDocumentV2, type RichTextDocument } from './model';
import { setDocumentAlignment, setDocumentHeading, toggleInlineMark, toggleList, updateRichTextText } from './richText';
import RichTextEditor, { RichTextToolbar } from './RichTextEditor';
import ReportChart from './ReportChart';

type Props = { runId: string; language: Language };
type SaveState = 'clean' | 'dirty' | 'saving' | 'saved' | 'error' | 'conflict';
type TextBlock = Extract<ReportBlock, { type: 'header' | 'text' | 'note' }>;
type RichCommand = 'bold' | 'italic' | 'underline' | 'bulletList' | 'orderedList' | 'heading' | 'paragraph' | 'left' | 'center' | 'right' | 'sm' | 'base' | 'lg' | 'xl';

const templates = [
  ['executive_briefing', 'Executive Briefing', 'Cover → KPI → synthesis → drivers → actions'],
  ['sales_performance_review', 'Sales Performance Review', 'Asymmetric trend → drivers → evidence table'],
  ['category_division_deep_dive', 'Category / Division Deep Dive', 'Scope → segment ranking → comparison → glossary'],
  ['weekly_monthly_business_review', 'Weekly / Monthly Business Review', 'Period snapshot → trends → decisions → owners'],
] as const;
const safeId = (prefix: string) => `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
const isTextBlock = (block: ReportBlock): block is TextBlock => block.type === 'header' || block.type === 'text' || block.type === 'note';
const numberValue = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value : 0;
const chartFor = (document: ReportDocumentV2, artifactId: string): ChartResult | undefined => {
  const artifact = artifactFor(document, artifactId);
  if (artifact?.presentation) return { ...((artifact.result ?? {}) as ChartResult), presentation: artifact.presentation };
  const result = artifact?.result;
  return result as ChartResult | undefined;
};
const displayMetric = (artifact: ReturnType<typeof artifactFor>) => {
  const result = artifact?.result as unknown as Record<string, unknown> | undefined;
  return String(result?.metric_display_name ?? result?.metric ?? 'Value');
};
const defaultGeometry = (type: ReportBlock['type'], index: number) => {
  if (type === 'chart') return { x: 0, y: index * 8, w: 8, h: 9 };
  if (type === 'data_table') return { x: 0, y: index * 8, w: 12, h: 9 };
  if (type === 'divider') return { x: 0, y: index * 4, w: 12, h: 2 };
  return { x: 0, y: index * 5, w: 12, h: 4 };
};

export default function ReportBuilder({ runId, language }: Props) {
  const [document, setDocument] = useState<ReportDocumentV2>(() => emptyReportV2(runId));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pageId, setPageId] = useState('page-1');
  const [state, setState] = useState<SaveState>('clean');
  const [message, setMessage] = useState('');
  const [preview, setPreview] = useState(false);
  const [history, setHistory] = useState<ReportDocumentV2[]>([]);
  const [future, setFuture] = useState<ReportDocumentV2[]>([]);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [showPageManager, setShowPageManager] = useState(false);
  const [pageDrafts, setPageDrafts] = useState<Record<string, string>>({});
  const [builderWidth, setBuilderWidth] = useState(1600);
  const [gridWidth, setGridWidth] = useState(760);

  const loaded = useRef(false);
  const documentRef = useRef(document);
  const persistedRevision = useRef(document.revision);
  const pending = useRef<ReportDocumentV2 | null>(null);
  const saveQueue = useRef<Promise<void>>(Promise.resolve());
  const builderRef = useRef<HTMLElement>(null);
  const gridHostRef = useRef<HTMLDivElement>(null);
  const richTextTimers = useRef<Record<string, number>>({});

  const mode = builderWidth >= 1600 ? 'wide' : builderWidth >= 1100 ? 'compact' : 'narrow';

  useEffect(() => {
    const node = builderRef.current;
    if (!node) return;
    const update = () => setBuilderWidth(Math.max(1, Math.floor(node.getBoundingClientRect().width)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const node = gridHostRef.current;
    if (!node) return;
    const update = () => setGridWidth(Math.max(1, Math.floor(node.getBoundingClientRect().width)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, [libraryOpen, inspectorOpen, preview]);

  useEffect(() => {
    let active = true;
    loaded.current = false;
    setSelectedId(null);
    void getReportV2(runId).then(next => {
      if (!active) return;
      documentRef.current = next;
      persistedRevision.current = next.revision;
      setDocument(next);
      setPageId(next.pages[0]?.page_id ?? 'page-1');
      setHistory([]);
      setFuture([]);
      setState('clean');
      setMessage('');
      loaded.current = true;
    }).catch(error => {
      if (active) setMessage(error instanceof Error ? error.message : 'Unable to load the report builder.');
    });
    return () => { active = false; };
  }, [runId]);

  const commit = useCallback((next: ReportDocumentV2, dirty = true) => {
    setHistory(previous => [...previous.slice(-29), documentRef.current]);
    setFuture([]);
    documentRef.current = next;
    setDocument(next);
    if (dirty && loaded.current) setState('dirty');
  }, []);

  const persist = useCallback((next: ReportDocumentV2): Promise<void> => {
    setState('saving');
    setMessage('');
    pending.current = next;
    const operation = saveQueue.current.catch(() => undefined).then(async () => {
      const queued = { ...next, revision: persistedRevision.current };
      const saved = await saveReportV2(runId, queued);
      persistedRevision.current = saved.revision;
      const isLatestDraft = documentRef.current === next;
      const wasPending = pending.current === next;
      if (isLatestDraft) {
        documentRef.current = saved;
        setDocument(saved);
      }
      if (wasPending) {
        pending.current = null;
        setState(isLatestDraft ? 'saved' : 'dirty');
        setMessage(isLatestDraft ? 'Saved' : 'Unsaved changes');
      }
    }).catch(error => {
      if (pending.current === next) {
        setState(error instanceof Error && error.message.includes('(409)') ? 'conflict' : 'error');
        setMessage(error instanceof Error ? error.message : 'Unable to save report.');
      }
      throw error;
    });
    saveQueue.current = operation;
    return operation;
  }, [runId]);

  const persistLatest = useCallback((): Promise<void> => persist(documentRef.current), [persist]);

  const mutate = useCallback((updater: (current: ReportDocumentV2) => ReportDocumentV2, save = true) => {
    const current = documentRef.current;
    const next = updater(current);
    if (next === current) return;
    commit(next);
    if (save) void persist(next).catch(() => undefined);
  }, [commit, persist]);

  const scheduleRichTextSave = useCallback((blockId: string, immediate = false) => {
    const previous = richTextTimers.current[blockId];
    if (previous) window.clearTimeout(previous);
    if (immediate) {
      persistLatest();
      return;
    }
    richTextTimers.current[blockId] = window.setTimeout(() => {
      delete richTextTimers.current[blockId];
      persistLatest();
    }, 500);
  }, [persistLatest]);

  const currentPage = [...document.pages].sort((left, right) => left.order - right.order).find(page => page.page_id === pageId) ?? [...document.pages].sort((left, right) => left.order - right.order)[0];
  const pageBlocks = useMemo(() => document.blocks.filter(block => document.placements.some(item => item.page_id === currentPage?.page_id && item.block_id === block.block_id)), [document, currentPage?.page_id]);
  const selected = selectedId ? blockFor(document, selectedId) : undefined;

  const addBlock = (type: ReportBlock['type'], artifactId?: string) => {
    const current = documentRef.current;
    const blockId = safeId(type);
    const index = current.blocks.length;
    let block: ReportBlock;
    if (type === 'header') block = { type, block_id: blockId, text: 'New section', level: 2 };
    else if (type === 'text') block = { type, block_id: blockId, text: 'Add evidence-grounded commentary.' };
    else if (type === 'note') block = { type, block_id: blockId, text: 'Add a note or watchout.', tone: 'info' };
    else if (type === 'divider') block = { type, block_id: blockId, style: 'solid', thickness: 1, color: 'slate' };
    else if (type === 'kpi_strip') block = { type, block_id: blockId, artifact_ids: artifactId ? [artifactId] : [], items: artifactId ? [{ artifact_id: artifactId }] : [] };
    else if (type === 'action_table') block = { type, block_id: blockId, rows: [] };
    else if (type === 'glossary') block = { type, block_id: blockId, artifact_ids: current.artifact_library.map(item => item.artifact_id), manual_note_ids: [], authored_notes: [] };
    else if (artifactId && type === 'chart') block = { type: 'chart', block_id: blockId, artifact_id: artifactId, view: 'chart', title: '' };
    else if (artifactId && type === 'data_table') block = { type: 'data_table', block_id: blockId, artifact_id: artifactId, view: 'table', title: '', visible_rows: 10 };
    else return;
    const targetPage = current.pages.find(page => page.page_id === pageId)?.page_id ?? current.pages[0].page_id;
    const geometry = defaultGeometry(type, index);
    mutate(next => ({ ...next, blocks: [...next.blocks, block], placements: [...next.placements, { block_id: blockId, page_id: targetPage, ...geometry }] }));
    setSelectedId(blockId);
  };

  const removeSelected = () => {
    if (!selectedId) return;
    mutate(current => ({ ...current, blocks: current.blocks.filter(block => block.block_id !== selectedId), placements: current.placements.filter(item => item.block_id !== selectedId) }));
    setSelectedId(null);
  };

  const duplicateSelected = () => {
    if (!selected) return;
    const current = documentRef.current;
    const blockId = safeId(selected.type);
    const placement = placementFor(current, selected.block_id);
    mutate(next => ({
      ...next,
      blocks: [...next.blocks, { ...selected, block_id: blockId } as ReportBlock],
      placements: [...next.placements, { ...(placement ?? { page_id: currentPage?.page_id ?? 'page-1', x: 0, y: 0, w: 6, h: 4 }), block_id: blockId, y: (placement?.y ?? 0) + (placement?.h ?? 4) }],
    }));
    setSelectedId(blockId);
  };

  const addPage = () => {
    const current = documentRef.current;
    const nextPage = { page_id: safeId('page'), title: `Page ${current.pages.length + 1}`, order: current.pages.length };
    mutate(next => ({ ...next, pages: [...next.pages, nextPage] }));
    setPageId(nextPage.page_id);
  };

  const renamePage = (pageKey: string, title: string) => {
    const nextTitle = title.trim() || 'Untitled page';
    mutate(current => ({ ...current, pages: current.pages.map(page => page.page_id === pageKey ? { ...page, title: nextTitle } : page) }));
  };

  const reorderPage = (pageKey: string, direction: -1 | 1) => {
    const ordered = [...documentRef.current.pages].sort((left, right) => left.order - right.order);
    const index = ordered.findIndex(page => page.page_id === pageKey);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    mutate(current => ({ ...current, pages: ordered.map((page, order) => ({ ...page, order })) }));
  };

  const deletePage = (pageKey: string) => {
    const current = documentRef.current;
    if (current.pages.length <= 1) return;
    const page = current.pages.find(item => item.page_id === pageKey);
    if (!page) return;
    const fallback = current.pages.find(item => item.page_id !== pageKey);
    if (!fallback) return;
    const hasBlocks = current.placements.some(item => item.page_id === pageKey);
    if (hasBlocks && !window.confirm(`Delete ${page.title} and move its blocks to ${fallback.title}?`)) return;
    mutate(next => ({
      ...next,
      pages: next.pages.filter(item => item.page_id !== pageKey).map((item, order) => ({ ...item, order })),
      placements: next.placements.map(item => item.page_id === pageKey ? { ...item, page_id: fallback.page_id } : item),
    }));
    if (pageId === pageKey) setPageId(fallback.page_id);
  };

  const changeLayout = (layout: Layout[]) => {
    const current = documentRef.current;
    const visibleIds = new Set(pageBlocks.map(block => block.block_id));
    const nextPlacements = current.placements.map(item => {
      if (!visibleIds.has(item.block_id)) return item;
      const changed = layout.find(entry => entry.i === item.block_id);
      return changed ? { ...item, x: changed.x, y: changed.y, w: changed.w, h: changed.h } : item;
    });
    const changed = nextPlacements.some((item, index) => {
      const previous = current.placements[index];
      return !previous || item.block_id !== previous.block_id || item.page_id !== previous.page_id || item.x !== previous.x || item.y !== previous.y || item.w !== previous.w || item.h !== previous.h;
    });
    if (!changed) return;
    const next = { ...current, placements: nextPlacements };
    commit(next);
    void persist(next).catch(() => undefined);
  };

  const updateRichText = (blockId: string, nextRichText: RichTextDocument, immediate = false) => {
    mutate(current => ({ ...current, blocks: current.blocks.map(block => block.block_id === blockId && isTextBlock(block) ? withRichText(block, nextRichText) : block) }), false);
    scheduleRichTextSave(blockId, immediate);
  };

  const applyRichCommand = (command: RichCommand) => {
    if (!selected || !isTextBlock(selected)) return;
    const currentText = richTextFor(selected);
    const next = command === 'left' || command === 'center' || command === 'right'
      ? setDocumentAlignment(currentText, command)
      : command === 'heading'
        ? setDocumentHeading(currentText, selected.type === 'header' ? selected.level : 2)
        : command === 'paragraph'
          ? setDocumentHeading(currentText, null)
          : command === 'bulletList' || command === 'orderedList'
            ? toggleList(currentText, command)
            : command === 'sm' || command === 'base' || command === 'lg' || command === 'xl'
              ? toggleInlineMark(currentText, 'fontSize', command)
              : toggleInlineMark(currentText, command);
    updateRichText(selected.block_id, next, true);
  };

  const updateSelectedText = (value: string) => {
    if (!selected || !isTextBlock(selected)) return;
    updateRichText(selected.block_id, updateRichTextText(richTextFor(selected), value, selected.type, selected.type === 'header' ? selected.level : 2));
  };

  const updateSelected = (updater: (block: ReportBlock) => ReportBlock) => {
    if (!selected) return;
    mutate(current => ({ ...current, blocks: current.blocks.map(block => block.block_id === selected.block_id ? updater(block) : block) }));
  };

  const applyTemplate = async (template: string) => {
    if (!window.confirm('Replace canvas layout and keep Library?')) return;
    setState('saving');
    setMessage('');
    const operation = saveQueue.current.catch(() => undefined).then(async () => {
      const next = await applyTemplateV2(runId, persistedRevision.current, template);
      documentRef.current = next;
      persistedRevision.current = next.revision;
      setDocument(next);
      setPageId(next.pages[0]?.page_id ?? 'page-1');
      setHistory(previous => [...previous.slice(-29), document]);
      setFuture([]);
      setState('saved');
      setMessage('Saved');
    }).catch(error => {
      setState(error instanceof Error && error.message.includes('(409)') ? 'conflict' : 'error');
      setMessage(error instanceof Error ? error.message : 'Unable to apply template.');
      throw error;
    });
    saveQueue.current = operation;
    await operation.catch(() => undefined);
  };

  const exportReport = async () => {
    setState('saving');
    try {
      await persist(documentRef.current);
      const result = await createReportExport(runId, persistedRevision.current);
      window.open(`/api/runs/${runId}/custom-report/exports/${result.export_id}`, '_blank', 'noopener,noreferrer');
      setState('saved');
      setMessage(`Exported revision ${result.revision}`);
    } catch (error) {
      setState('error');
      setMessage(error instanceof Error ? error.message : 'Unable to export this report.');
    }
  };

  const statusLabel = state === 'dirty' ? 'Unsaved changes' : state === 'saving' ? 'Saving…' : state === 'conflict' ? 'Conflict — reload required' : message || (state === 'saved' ? 'Saved' : 'Ready');
  const sortedPages = [...document.pages].sort((left, right) => left.order - right.order);

  return <section ref={builderRef} className="report-builder" data-report-mode={mode} data-report-revision={document.revision}>
    <header className="report-builder-toolbar">
      <div className="report-builder-title-group"><p className="section-eyebrow">Report Builder v2</p><input className="report-name-input" aria-label="Report name" value={document.title} onChange={event => mutate(current => ({ ...current, title: event.target.value }), false)} onBlur={() => { void persistLatest().catch(() => undefined); }}/><span className={`report-save-state report-save-${state}`} aria-live="polite">{statusLabel}</span></div>
      <div className="report-toolbar-actions">
        <button type="button" className="report-panel-toggle" aria-expanded={libraryOpen} onClick={() => setLibraryOpen(value => !value)}>{libraryOpen ? 'Hide library' : 'Show library'}</button>
        <button type="button" className="report-panel-toggle" aria-expanded={inspectorOpen} onClick={() => setInspectorOpen(value => !value)}>{inspectorOpen ? 'Hide inspector' : 'Show inspector'}</button>
        <button type="button" onClick={() => setShowPageManager(value => !value)}>Pages</button>
        <button type="button" onClick={() => setPreview(value => !value)}>{preview ? 'Edit' : 'Preview'}</button>
        <button type="button" onClick={() => { const previous = history.at(-1); if (!previous) return; setFuture(items => [...items, documentRef.current]); setHistory(items => items.slice(0, -1)); documentRef.current = previous; setDocument(previous); setState('dirty'); }} disabled={!history.length} title="Undo"><Undo2 size={15}/></button>
        <button type="button" onClick={() => { const next = future.at(-1); if (!next) return; setHistory(items => [...items, documentRef.current]); setFuture(items => items.slice(0, -1)); documentRef.current = next; setDocument(next); setState('dirty'); }} disabled={!future.length} title="Redo"><Redo2 size={15}/></button>
        <button type="button" onClick={persistLatest}><Save size={15}/>Save</button>
        <button type="button" onClick={() => void exportReport()}><Download size={15}/>Export HTML</button>
      </div>
    </header>

    {showPageManager && <section className="report-page-manager" aria-label="Page manager"><div className="report-page-manager-heading"><div><p className="section-eyebrow">Report pages</p><h2>Rename and reorder pages</h2></div><button type="button" onClick={() => setShowPageManager(false)}>Done</button></div>{sortedPages.map((page, index) => <div className="report-page-manager-row" key={page.page_id}><input aria-label={`Rename ${page.title}`} value={pageDrafts[page.page_id] ?? page.title} onChange={event => setPageDrafts(current => ({ ...current, [page.page_id]: event.target.value }))} onKeyDown={event => { if (event.key === 'Enter') { renamePage(page.page_id, event.currentTarget.value); persistLatest(); event.currentTarget.blur(); } if (event.key === 'Escape') { setPageDrafts(current => { const next = { ...current }; delete next[page.page_id]; return next; }); event.currentTarget.blur(); } }} onBlur={event => { renamePage(page.page_id, event.target.value); persistLatest(); }}/><button type="button" onClick={() => reorderPage(page.page_id, -1)} disabled={index === 0} aria-label={`Move ${page.title} earlier`}><ChevronLeft size={14}/></button><button type="button" onClick={() => reorderPage(page.page_id, 1)} disabled={index === sortedPages.length - 1} aria-label={`Move ${page.title} later`}><ChevronRight size={14}/></button><button type="button" onClick={() => deletePage(page.page_id)} disabled={sortedPages.length <= 1}>Delete</button></div>)}</section>}

    <div data-report-mode={mode} className={`report-builder-shell ${preview ? 'is-preview' : ''} ${libraryOpen ? 'library-visible' : ''} ${inspectorOpen ? 'inspector-visible' : ''}`}>
      {!preview && libraryOpen && <aside className="report-library" aria-label="Report Library"><div className="report-panel-heading"><div><p className="section-eyebrow">Reusable items</p><h2>Library</h2></div><button type="button" onClick={addPage} title="Add page"><Plus size={15}/></button></div><div className="library-group"><b>Blocks</b>{(['header', 'text', 'note', 'divider', 'kpi_strip', 'action_table', 'glossary'] as ReportBlock['type'][]).map(type => <button type="button" key={type} onClick={() => addBlock(type)}><Plus size={13}/>{type.replace('_', ' ')}</button>)}</div><div className="library-group"><b>Charts & tables</b>{document.artifact_library.map(item => <div className="library-artifact" key={item.artifact_id}><span><strong>{String(item.provenance.title || (item.result as unknown as Record<string, unknown> | undefined)?.title || item.artifact_id)}</strong><small>{item.origin} · {item.result?.request?.date_scope ? 'saved scope' : 'all data'}</small></span><button type="button" onClick={() => addBlock('chart', item.artifact_id)} aria-label={`Add ${item.artifact_id} chart`}><Plus size={13}/>Chart</button><button type="button" onClick={() => addBlock('data_table', item.artifact_id)} aria-label={`Add ${item.artifact_id} table`}>Table</button></div>)}</div><div className="library-group"><b>Templates</b>{templates.map(([id, title, description]) => <button type="button" className="template-choice" key={id} onClick={() => void applyTemplate(id)}><LayoutTemplate size={14}/><span><strong>{title}</strong><small>{description}</small></span></button>)}</div></aside>}

      <main className="report-canvas-area"><div className="report-page-tabs">{sortedPages.map(page => <button type="button" key={page.page_id} className={page.page_id === currentPage?.page_id ? 'active' : ''} onClick={() => setPageId(page.page_id)}>{page.title}</button>)}<button type="button" onClick={addPage} aria-label="Add page"><Plus size={13}/></button></div><div className={`report-canvas ${preview ? 'report-canvas-preview' : ''}`}><div ref={gridHostRef} className="report-grid-host"><GridLayout className="report-grid-layout" layout={pageBlocks.map(block => { const item = placementFor(document, block.block_id)!; return { i: block.block_id, x: item.x, y: item.y, w: item.w, h: item.h, minW: block.type === 'chart' ? 4 : 2, minH: block.type === 'chart' ? 6 : block.type === 'divider' ? 1 : 2 }; })} cols={12} rowHeight={document.page_settings.row_height} width={gridWidth} margin={[document.page_settings.gap, document.page_settings.gap]} isDraggable={!preview} isResizable={!preview} isBounded={true} draggableHandle=".report-block-drag-handle" draggableCancel=".report-inline-editor, .report-rich-editor, input, textarea, select, button, table, a" compactType={null} preventCollision={true} onLayoutChange={changeLayout}>{pageBlocks.map(block => <article key={block.block_id} className={`report-block report-block-${block.type} ${selectedId === block.block_id ? 'selected' : ''} ${block.type === 'note' ? `report-block-tone-${block.tone}` : ''}`} onClick={() => setSelectedId(current => current === block.block_id ? current : block.block_id)}><div className="report-block-handle report-block-drag-handle"><GripVertical size={14}/><span>{block.type.replace('_', ' ')}</span></div><BlockView block={block} document={document} language={language} readOnly={preview} onTextChange={(next: RichTextDocument) => updateRichText(block.block_id, next)} onTextBlur={() => scheduleRichTextSave(block.block_id, true)}/></article>)}</GridLayout>{!pageBlocks.length && <div className="report-empty-canvas"><Plus size={18}/><p>Add a block or validated artifact from Library.</p></div>}</div></div></main>

      {!preview && inspectorOpen && <aside className="report-inspector"><div className="report-panel-heading"><div><p className="section-eyebrow">Selected block</p><h2>Inspector</h2></div></div>{selected ? <><p className="inspector-type">{selected.type} · {selected.block_id}</p>{isTextBlock(selected) && <><RichTextToolbar onCommand={applyRichCommand}/><label className="inspector-field">Content<textarea value={selected.text} onChange={event => updateSelectedText(event.target.value)} onBlur={() => scheduleRichTextSave(selected.block_id, true)} rows={5}/></label></>}{selected.type === 'note' && <label className="inspector-field">Tone<select value={selected.tone} onChange={event => updateSelected(block => block.type === 'note' ? { ...block, tone: event.target.value as typeof block.tone } : block)}><option value="neutral">Neutral</option><option value="info">Info</option><option value="warning">Warning</option><option value="success">Success</option></select></label>}{selected.type === 'divider' && <div className="divider-controls"><label className="inspector-field">Style<select value={selected.style ?? 'solid'} onChange={event => updateSelected(block => block.type === 'divider' ? { ...block, style: event.target.value as typeof block.style } : block)}><option value="solid">Solid</option><option value="dashed">Dashed</option><option value="dotted">Dotted</option></select></label><label className="inspector-field">Thickness<select value={selected.thickness ?? 1} onChange={event => updateSelected(block => block.type === 'divider' ? { ...block, thickness: Number(event.target.value) as 1 | 2 | 3 } : block)}><option value="1">1px</option><option value="2">2px</option><option value="3">3px</option></select></label><label className="inspector-field">Color<select value={selected.color ?? 'slate'} onChange={event => updateSelected(block => block.type === 'divider' ? { ...block, color: event.target.value as typeof block.color } : block)}><option value="slate">Slate</option><option value="indigo">Indigo</option><option value="amber">Amber</option></select></label></div>}{selected.type === 'action_table' && <ActionTableEditor block={selected} onChange={rows => mutate(current => ({ ...current, blocks: current.blocks.map(block => block.block_id === selected.block_id && block.type === 'action_table' ? { ...block, rows } : block) }))}/>} {selected.type === 'kpi_strip' && <KpiStripEditor block={selected} artifacts={document.artifact_library} onChange={next => updateSelected(() => next)}/>} {selected.type === 'glossary' && <GlossaryEditor block={selected} onChange={next => updateSelected(() => next)}/>} {(selected.type === 'chart' || selected.type === 'data_table') && <><label className="inspector-field">Title<input value={selected.title} onChange={event => updateSelected(block => (block.type === 'chart' || block.type === 'data_table') ? { ...block, title: event.target.value } : block)} onBlur={() => { void persistLatest().catch(() => undefined); }}/></label>{selected.type === 'data_table' && <label className="inspector-field">Visible rows<input type="number" min={1} max={100} value={selected.visible_rows ?? 10} onChange={event => updateSelected(block => block.type === 'data_table' ? { ...block, visible_rows: Math.min(100, Math.max(1, Number(event.target.value) || 1)) } : block)} /></label>}<p className="inspector-scope">Validated artifact: {selected.artifact_id}<br/>{String(artifactFor(document, selected.artifact_id)?.provenance.scope ?? '')}</p></>}<div className="inspector-actions"><button type="button" onClick={duplicateSelected}><Copy size={14}/>Duplicate</button><button type="button" onClick={removeSelected} className="danger"><Trash2 size={14}/>Delete</button></div></> : <p className="inspector-empty">Select a block on the canvas to edit, duplicate, or delete it.</p>}</aside>}
    </div>
  </section>;
}

function BlockView({ block, document, language, readOnly, onTextChange, onTextBlur }: { block: ReportBlock; document: ReportDocumentV2; language: Language; readOnly: boolean; onTextChange: (next: RichTextDocument) => void; onTextBlur: () => void }) {
  if (isTextBlock(block)) return <div className={`report-authored-content report-authored-${block.type}`}><RichTextEditor document={richTextFor(block)} onChange={onTextChange} onBlur={onTextBlur} readOnly={readOnly}/></div>;
  if (block.type === 'divider') return <hr style={{ borderTopStyle: block.style ?? 'solid', borderTopWidth: `${block.thickness ?? 1}px`, borderTopColor: block.color === 'indigo' ? '#6366f1' : block.color === 'amber' ? '#f59e0b' : '#94a3b8' }}/>;
  if (block.type === 'action_table') return <ActionTableView rows={block.rows}/>;
  if (block.type === 'glossary') return <GlossaryView block={block} document={document}/>;
  if (block.type === 'kpi_strip') return <KpiStripView block={block} document={document}/>;
  const chart = chartFor(document, block.artifact_id);
  if (!chart) return <div className="report-placeholder">Validated artifact is unavailable.</div>;
  if (block.type === 'chart') return <ReportChart result={chart} language={language}/>;
  return <div className="report-table-preview"><strong>{block.title || chart.title}</strong><table><thead><tr><th>Label</th><th>{displayMetric(artifactFor(document, block.artifact_id))}</th></tr></thead><tbody>{chart.rows.slice(0, block.visible_rows ?? 10).map((row, index) => <tr key={`${row.label}-${index}`}><td>{row.display_label ?? row.label}</td><td>{row.formatted_value ?? numberValue(row.value)}</td></tr>)}</tbody></table></div>;
}

function ActionTableView({ rows }: { rows: ReportBlock extends never ? never : Array<{ owner: string; action: string; deadline: string; status: string }> }) {
  return <div className="action-table-view">{rows.length ? <table><thead><tr><th>Owner</th><th>Action</th><th>Deadline</th><th>Status</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.owner}-${index}`}><td>{row.owner}</td><td>{row.action}</td><td>{row.deadline}</td><td><span className={`action-status action-${row.status}`}>{row.status.replace('_', ' ')}</span></td></tr>)}</tbody></table> : <p className="action-empty">Add an action row in the Inspector.</p>}</div>;
}

function ActionTableEditor({ block, onChange }: { block: Extract<ReportBlock, { type: 'action_table' }>; onChange: (rows: Extract<ReportBlock, { type: 'action_table' }>['rows']) => void }) {
  const update = (index: number, key: 'owner' | 'action' | 'deadline' | 'status', value: string) => onChange(block.rows.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row));
  const addRow = () => onChange([...block.rows, { owner: '', action: '', deadline: '', status: 'not_started' }]);
  const moveRow = (index: number, direction: -1 | 1) => { const target = index + direction; if (target < 0 || target >= block.rows.length) return; const rows = [...block.rows]; [rows[index], rows[target]] = [rows[target], rows[index]]; onChange(rows); };
  return <div className="action-table-editor"><div className="inspector-subheading"><b>Action rows</b><button type="button" onClick={addRow}>Add row</button></div>{block.rows.map((row, index) => <div className="action-editor-row" key={index}><input aria-label={`Owner ${index + 1}`} value={row.owner} placeholder="Owner" onChange={event => update(index, 'owner', event.target.value)}/><input aria-label={`Action ${index + 1}`} value={row.action} placeholder="Action" onChange={event => update(index, 'action', event.target.value)}/><input aria-label={`Deadline ${index + 1}`} type="date" value={row.deadline} onChange={event => update(index, 'deadline', event.target.value)}/><select aria-label={`Status ${index + 1}`} value={row.status} onChange={event => update(index, 'status', event.target.value)} onKeyDown={event => { if (event.key === 'Tab' && index === block.rows.length - 1) addRow(); }}><option value="not_started">Not started</option><option value="in_progress">In progress</option><option value="blocked">Blocked</option><option value="done">Done</option></select><span className="action-row-controls"><button type="button" onClick={() => moveRow(index, -1)} disabled={index === 0} aria-label={`Move action ${index + 1} earlier`}>↑</button><button type="button" onClick={() => moveRow(index, 1)} disabled={index === block.rows.length - 1} aria-label={`Move action ${index + 1} later`}>↓</button><button type="button" aria-label={`Delete action ${index + 1}`} onClick={() => onChange(block.rows.filter((_, rowIndex) => rowIndex !== index))}>×</button></span></div>)}</div>;
}

function KpiStripView({ block, document }: { block: Extract<ReportBlock, { type: 'kpi_strip' }>; document: ReportDocumentV2 }) {
  const ids = block.items?.length ? block.items.map(item => item.artifact_id) : block.artifact_ids;
  return <div className="kpi-strip-preview">{ids.map(id => { const artifact = artifactFor(document, id); const result = artifact?.result as unknown as Record<string, unknown> | undefined; const row = (result?.rows as Array<Record<string, unknown>> | undefined)?.[0]; const item = block.items?.find(entry => entry.artifact_id === id); return <span key={id}><small>{item?.label_override || String(result?.metric_display_name || result?.metric || result?.title || id)}</small><strong>{String(result?.scope_total_formatted_value ?? result?.scope_total_value ?? row?.formatted_value ?? '—')}</strong>{result?.change_pct != null && <em>{Number(result.change_pct) > 0 ? '+' : ''}{String(result.change_pct)}%</em>}</span>; })}</div>;
}

function KpiStripEditor({ block, artifacts, onChange }: { block: Extract<ReportBlock, { type: 'kpi_strip' }>; artifacts: ReportDocumentV2['artifact_library']; onChange: (next: Extract<ReportBlock, { type: 'kpi_strip' }>) => void }) {
  const ids = block.items?.length ? block.items.map(item => item.artifact_id) : block.artifact_ids;
  const add = (artifactId: string) => { if (!artifactId || ids.includes(artifactId)) return; const nextIds = [...ids, artifactId].slice(0, 4); onChange({ ...block, artifact_ids: nextIds, items: nextIds.map(id => block.items?.find(item => item.artifact_id === id) ?? { artifact_id: id }) }); };
  const remove = (artifactId: string) => { const nextIds = ids.filter(id => id !== artifactId); onChange({ ...block, artifact_ids: nextIds, items: nextIds.map(id => block.items?.find(item => item.artifact_id === id) ?? { artifact_id: id }) }); };
  return <div className="kpi-editor"><label className="inspector-field">Add validated KPI<select value="" onChange={event => add(event.target.value)}><option value="">Choose artifact…</option>{artifacts.filter(item => !ids.includes(item.artifact_id)).map(item => <option key={item.artifact_id} value={item.artifact_id}>{String(item.provenance.title || item.artifact_id)}</option>)}</select></label>{ids.map(id => <div className="kpi-editor-row" key={id}><span>{id}</span><button type="button" onClick={() => remove(id)}>Remove</button></div>)}</div>;
}

function GlossaryView({ block, document }: { block: Extract<ReportBlock, { type: 'glossary' }>; document: ReportDocumentV2 }) {
  const entries = block.artifact_ids.map(id => { const result = artifactFor(document, id)?.result as unknown as Record<string, unknown> | undefined; return result ? { label: String(result.dimension_display_name || result.dimension || id), description: `${String(result.metric_display_name || result.metric || 'Metric')} · ${String(result.aggregation || 'aggregate')}` } : null; }).filter(Boolean) as Array<{ label: string; description: string }>;
  return <div className="glossary-view"><h3>Glossary</h3><dl>{entries.map(entry => <div key={`${entry.label}-${entry.description}`}><dt>{entry.label}</dt><dd>{entry.description}</dd></div>)}{block.authored_notes?.map(note => <div key={note.note_id}><dt>Author note</dt><dd>{note.text}</dd></div>)}</dl>{!entries.length && !block.authored_notes?.length && <p className="action-empty">Add a validated artifact or authored note.</p>}</div>;
}

function GlossaryEditor({ block, onChange }: { block: Extract<ReportBlock, { type: 'glossary' }>; onChange: (next: Extract<ReportBlock, { type: 'glossary' }>) => void }) {
  const [note, setNote] = useState('');
  const add = () => { const text = note.trim(); if (!text) return; onChange({ ...block, authored_notes: [...(block.authored_notes ?? []), { note_id: safeId('glossary-note'), text }] }); setNote(''); };
  return <div className="glossary-editor"><label className="inspector-field">Add authored note<textarea value={note} rows={3} onChange={event => setNote(event.target.value)} /></label><button type="button" onClick={add}>Add note</button></div>;
}
