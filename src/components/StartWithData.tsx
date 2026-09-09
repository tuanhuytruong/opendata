import { useState } from 'react';
import type { ReactNode } from 'react';
import { Bot, CheckCircle2, ChevronRight, FileText, LayoutDashboard, LoaderCircle, Sparkles, Upload } from 'lucide-react';

import DatasetSelector from './DatasetSelector';
import { DatasetProfile } from '../types';
import { displayNumber, Language, text } from '../i18n';

type Props = {
  language: Language;
  profile: DatasetProfile | null;
  selectedFile: File | null;
  loading: boolean;
  onUploadStart: (file: File) => void;
  onProfile: (profile: DatasetProfile) => void;
};

type DemoView = {
  id: 'revenue' | 'orders' | 'conversion';
  label: string;
  metric: string;
  trend: string;
  detailLabel: string;
  values: number[];
  labels: string[];
};

const demoViews: DemoView[] = [
  { id: 'revenue', label: 'Revenue', values: [42, 53, 48, 66, 61, 78], labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], metric: '$24.8k', trend: '+18.4%', detailLabel: 'Jun' },
  { id: 'orders', label: 'Orders', values: [1284, 1098, 862, 740, 623], labels: ['Online', 'Retail', 'Partner', 'Direct', 'Other'], metric: '1,284', trend: '+9.2%', detailLabel: 'Online' },
  { id: 'conversion', label: 'Conversion', values: [48, 31, 21], labels: ['Returning', 'New', 'Assisted'], metric: '4.8%', trend: '+0.7 pp', detailLabel: 'Returning' },
];

export default function StartWithData({ language, profile, selectedFile, loading, onUploadStart, onProfile }: Props) {
  const t = (key: Parameters<typeof text>[1]) => text(language, key);
  const isProfiling = Boolean(profile || selectedFile);
  const complete = profile?.profile_status === 'complete';
  return <main className="start-canvas">
    <section className="start-hero" aria-labelledby="start-title">
      <div className="start-copy">
        <p className="section-eyebrow">{t('startEyebrow')}</p>
        <h1 id="start-title" className="font-display">{isProfiling ? t('profileTitle') : t('startTitle')}</h1>
        <p>{isProfiling ? t('profileSubtitle') : t('startSubtitle')}</p>
        {!isProfiling && <div className="start-actions"><a className="start-primary" href="#import-data"><Upload className="w-4 h-4" />{t('importData')}</a><a className="start-secondary" href="#demo-data"><Sparkles className="w-4 h-4" />{t('exploreDemo')}</a></div>}
        {!isProfiling && <p className="start-limits">{t('uploadHint')}</p>}
      </div>
      <DemoPreview language={language} />
    </section>
    {isProfiling ? <ProfilingPanel language={language} profile={profile} selectedFile={selectedFile} loading={loading} complete={complete} /> : <section id="import-data" className="start-import-section" aria-labelledby="import-title"><div><p className="section-eyebrow">{t('importData')}</p><h2 id="import-title" className="font-display">{t('importTitle')}</h2><p>{t('importSubtitle')}</p></div><DatasetSelector language={language} onUploadStart={onUploadStart} onProfile={onProfile} /></section>}
    {!isProfiling && <section className="product-preview" aria-labelledby="product-preview-title"><div><p className="section-eyebrow">{t('productEyebrow')}</p><h2 id="product-preview-title" className="font-display">{t('productTitle')}</h2></div><div className="product-preview-grid"><PreviewCard icon={<LayoutDashboard />} title={t('previewHubTitle')} body={t('previewHubBody')} /><PreviewCard icon={<Bot />} title={t('previewCopilotTitle')} body={t('previewCopilotBody')} /><PreviewCard icon={<FileText />} title={t('previewDeepDiveTitle')} body={t('previewDeepDiveBody')} /></div></section>}
  </main>;
}

function DemoPreview({ language }: { language: Language }) {
  const t = (key: Parameters<typeof text>[1]) => text(language, key);
  const [active, setActive] = useState(0);
  const [point, setPoint] = useState<number | null>(null);
  const view = demoViews[active];
  const selected = point === null ? view.values.length - 1 : point;
  const value = view.values[selected];
  return <section id="demo-data" className="demo-preview" aria-label={t('demoPreviewLabel')}>
    <div className="demo-preview-header"><span className="demo-badge">{t('demoData')}</span><span>{t('demoInteractive')}</span></div>
    <div className="demo-switcher" role="tablist" aria-label={t('demoSelectView')}>
      {demoViews.map((item, index) => <button type="button" role="tab" aria-selected={active === index} key={item.id} onClick={() => { setActive(index); setPoint(null); }}>{item.label}</button>)}
    </div>
    <DemoVisual view={view} point={point} onPoint={setPoint} />
    <div className="demo-selection" aria-live="polite"><span>{view.labels[selected]}</span><b>{formatDemoValue(view, value)}</b></div>
    <div className="demo-preview-stat"><div><small>{view.label}</small><b>{formatDemoValue(view, value)}</b></div><div><small>{t('demoTrend')}</small><b className="demo-positive">{view.trend}</b></div></div>
    <p>{t('demoDisclaimer')}</p>
    <a className="demo-start-link" href="#import-data"><Upload className="w-3.5 h-3.5" />{t('startYourData')}<ChevronRight className="w-3.5 h-3.5" /></a>
  </section>;
}

function formatDemoValue(view: DemoView, value: number) {
  if (view.id === 'revenue') return `$${value}k`;
  if (view.id === 'conversion') return `${value}%`;
  return value.toLocaleString('en-US');
}

function valueAt(view: DemoView, index: number) { return view.values[index]; }

function DemoVisual({ view, point, onPoint }: { view: DemoView; point: number | null; onPoint: (index: number | null) => void }) {
  const selected = point === null ? view.values.length - 1 : point;
  const activate = (index: number) => onPoint(index);
  if (view.id === 'revenue') {
    const width = 360; const height = 190; const plotLeft = 30; const plotRight = 330; const plotTop = 24; const plotBottom = 132; const axisY = 158;
    const max = Math.max(...view.values); const min = Math.min(...view.values); const spread = Math.max(1, max - min);
    const coords = view.values.map((value, index) => ({ x: plotLeft + index * ((plotRight - plotLeft) / (view.values.length - 1)), y: plotBottom - ((value - min) / spread) * (plotBottom - plotTop) }));
    const selectedCoord = coords[selected];
    return <div className="demo-chart demo-line-chart" role="group" aria-label={`${view.label} trend`}><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${view.label}: ${view.values.join(', ')}`}><line x1={plotLeft} x2={plotRight} y1={plotBottom} y2={plotBottom} className="demo-baseline"/><path d={`M ${coords.map(c => `${c.x} ${c.y}`).join(' L ')}`} className="demo-line-path" /><path d={`M ${coords[0].x} ${plotBottom} L ${coords.map(c => `${c.x} ${c.y}`).join(' L ')} L ${coords.at(-1)?.x} ${plotBottom} Z`} className="demo-area-fill" />{coords.map((coord, index) => <g key={view.labels[index]}><circle cx={coord.x} cy={coord.y} r={selected === index ? 5 : 3.5} className={selected === index ? 'selected' : ''} /><rect x={coord.x - 24} y={plotTop - 16} width="48" height={plotBottom - plotTop + 30} fill="transparent" tabIndex={0} role="button" aria-label={`${view.labels[index]}: ${formatDemoValue(view, view.values[index])}`} onMouseEnter={() => activate(index)} onFocus={() => activate(index)} onClick={() => activate(index)} /></g>)}<text x={selectedCoord.x} y={Math.max(16, selectedCoord.y - 12)} textAnchor="middle" className="demo-selected-value">{formatDemoValue(view, valueAt(view, selected))}</text>{coords.map((coord, index) => <text key={view.labels[index]} x={coord.x} y={axisY} textAnchor="middle" className="demo-axis-label">{view.labels[index]}</text>)}</svg></div>;
  }
  if (view.id === 'orders') {
    const max = Math.max(...view.values);
    return <div className="demo-chart demo-ranking-chart" role="group" aria-label={`${view.label} ranking`}>{view.values.map((value, index) => <button type="button" key={view.labels[index]} className={selected === index ? 'active' : ''} onMouseEnter={() => activate(index)} onFocus={() => activate(index)} onClick={() => activate(index)} aria-label={`${view.labels[index]}: ${formatDemoValue(view, value)}`}><span className="demo-rank-label">{view.labels[index]}</span><span className="demo-rank-track"><i style={{ width: `${(value / max) * 100}%` }} /></span><b>{formatDemoValue(view, value)}</b></button>)}</div>;
  }
  const circumference = 2 * Math.PI * 42;
  let offset = 0;
  return <div className="demo-chart demo-donut-chart" role="group" aria-label={`${view.label} share`}><svg viewBox="0 0 140 140" role="img"><circle cx="70" cy="70" r="42" className="demo-donut-base" />{view.values.map((value, index) => { const dash = circumference * (value / 100); const segment = <circle key={view.labels[index]} cx="70" cy="70" r="42" className={selected === index ? 'selected' : ''} strokeDasharray={`${dash} ${circumference - dash}`} strokeDashoffset={-offset} transform="rotate(-90 70 70)" tabIndex={0} role="button" aria-label={`${view.labels[index]}: ${formatDemoValue(view, value)}`} onMouseEnter={() => activate(index)} onFocus={() => activate(index)} onClick={() => activate(index)} />; offset += dash; return segment; })}<text x="70" y="65" textAnchor="middle" className="demo-donut-total">{view.metric}</text><text x="70" y="80" textAnchor="middle">conversion</text></svg><div className="demo-donut-legend">{view.labels.map((label, index) => <button type="button" key={label} className={selected === index ? 'active' : ''} onMouseEnter={() => activate(index)} onFocus={() => activate(index)} onClick={() => activate(index)}><i /><span>{label}</span><b>{view.values[index]}%</b></button>)}</div></div>;
}

function ProfilingPanel({ language, profile, selectedFile, loading, complete }: { language: Language; profile: DatasetProfile | null; selectedFile: File | null; loading: boolean; complete: boolean }) { const t = (key: Parameters<typeof text>[1]) => text(language, key); const schema = profile?.columns.slice(0, 5) ?? []; const fileName = profile?.file_name ?? selectedFile?.name ?? t('fileAccepted'); return <section className="profile-progress" aria-labelledby="profiling-title" aria-busy={loading}><div className="profile-file"><span className="profile-file-icon"><FileText className="w-5 h-5" /></span><div><p className="section-eyebrow">{t('fileAccepted')}</p><h2 id="profiling-title">{fileName}</h2>{profile ? <p>{displayNumber(profile.row_count, language)} {t('rows')} · {profile.column_count} {t('columns')}</p> : <p>{t('uploadingFile')}</p>}</div></div><div className="profile-stages" role="status" aria-live="polite"><Stage complete label={t('stageAccepted')} /><Stage complete={Boolean(profile?.row_count && profile.column_count)} busy={!profile} label={t('stageRecognized')} /><Stage complete={complete} busy={Boolean(profile) && loading} label={t('stageSchema')} /><Stage complete={complete && !loading} busy={Boolean(profile) && (!complete || loading)} label={t('stageExecutive')} /></div><div className="profile-schema"><div><p className="section-eyebrow">{t('recognizedSchema')}</p><h3>{complete ? t('schemaReady') : t('schemaPreparing')}</h3></div>{schema.length ? <div className="schema-chips">{schema.map(column => <span key={column.name}>{column.name}<em>{column.kind}</em></span>)}</div> : <SkeletonLines count={3} />}</div><div className="profile-skeletons" aria-label={t('executiveSkeletonLabel')}><SkeletonCard /><SkeletonCard /><SkeletonCard /></div><p className="profile-honesty">{t('profileHonesty')}</p></section>; }
function Stage({ complete, busy, label }: { complete: boolean; busy?: boolean; label: string }) { return <div className={complete ? 'done' : busy ? 'busy' : ''}>{complete ? <CheckCircle2 className="w-4 h-4" /> : busy ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <span className="stage-dot" />}<span>{label}</span></div>; }
function SkeletonLines({ count }: { count: number }) { return <div className="skeleton-lines">{Array.from({ length: count }, (_, index) => <span key={index} />)}</div>; }
function SkeletonCard() { return <div className="profile-skeleton-card" aria-hidden="true"><span /><span /><span /></div>; }
function PreviewCard({ icon, title, body }: { icon: ReactNode; title: string; body: string }) { return <article><span>{icon}</span><h3>{title}</h3><p>{body}</p></article>; }
