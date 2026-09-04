import type { ReactNode } from 'react';
import { Bot, CheckCircle2, FileText, LayoutDashboard, LoaderCircle, Sparkles, Upload } from 'lucide-react';

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

export default function StartWithData({ language, profile, selectedFile, loading, onUploadStart, onProfile }: Props) {
  const t = (key: Parameters<typeof text>[1]) => text(language, key);
  const isProfiling = Boolean(profile || selectedFile);
  const complete = profile?.profile_status === 'complete';
  const schema = profile?.columns.slice(0, 5) ?? [];

  return <main className="start-canvas">
    <section className="start-hero" aria-labelledby="start-title">
      <div className="start-copy">
        <p className="section-eyebrow">{t('startEyebrow')}</p>
        <h1 id="start-title" className="font-display">{isProfiling ? t('profileTitle') : t('startTitle')}</h1>
        <p>{isProfiling ? t('profileSubtitle') : t('startSubtitle')}</p>
        {!isProfiling && <div className="start-actions">
          <a className="start-primary" href="#import-data"><Upload className="w-4 h-4" />{t('importData')}</a>
          <a className="start-secondary" href="#demo-data"><Sparkles className="w-4 h-4" />{t('exploreDemo')}</a>
        </div>}
        {!isProfiling && <p className="start-limits">{t('uploadHint')}</p>}
      </div>
      <DemoPreview language={language} />
    </section>

    {isProfiling ? <ProfilingPanel language={language} profile={profile} selectedFile={selectedFile} loading={loading} complete={complete} /> : <section id="import-data" className="start-import-section" aria-labelledby="import-title">
      <div><p className="section-eyebrow">{t('importData')}</p><h2 id="import-title" className="font-display">{t('importTitle')}</h2><p>{t('importSubtitle')}</p></div>
      <DatasetSelector language={language} onUploadStart={onUploadStart} onProfile={onProfile} />
    </section>}

    {!isProfiling && <section className="product-preview" aria-labelledby="product-preview-title">
      <div><p className="section-eyebrow">{t('productEyebrow')}</p><h2 id="product-preview-title" className="font-display">{t('productTitle')}</h2></div>
      <div className="product-preview-grid">
        <PreviewCard icon={<LayoutDashboard />} title={t('previewHubTitle')} body={t('previewHubBody')} />
        <PreviewCard icon={<Bot />} title={t('previewCopilotTitle')} body={t('previewCopilotBody')} />
        <PreviewCard icon={<FileText />} title={t('previewDeepDiveTitle')} body={t('previewDeepDiveBody')} />
      </div>
    </section>}
  </main>;
}

function DemoPreview({ language }: { language: Language }) {
  const t = (key: Parameters<typeof text>[1]) => text(language, key);
  return <section id="demo-data" className="demo-preview" aria-label={t('demoPreviewLabel')}>
    <div className="demo-preview-header"><span className="demo-badge">{t('demoData')}</span><span>{t('demoPreviewLabel')}</span></div>
    <div className="demo-chart" aria-hidden="true"><span style={{ height: '37%' }} /><span style={{ height: '54%' }} /><span style={{ height: '46%' }} /><span style={{ height: '78%' }} /><span style={{ height: '64%' }} /><span style={{ height: '91%' }} /></div>
    <div className="demo-preview-stat"><div><small>{t('demoMetric')}</small><b>24.8k</b></div><div><small>{t('demoTrend')}</small><b className="demo-positive">+18.4%</b></div></div>
    <p>{t('demoDisclaimer')}</p>
    <a className="demo-start-link" href="#import-data"><Upload className="w-3.5 h-3.5" />{t('startYourData')}</a>
  </section>;
}

function ProfilingPanel({ language, profile, selectedFile, loading, complete }: { language: Language; profile: DatasetProfile | null; selectedFile: File | null; loading: boolean; complete: boolean }) {
  const t = (key: Parameters<typeof text>[1]) => text(language, key);
  const schema = profile?.columns.slice(0, 5) ?? [];
  const fileName = profile?.file_name ?? selectedFile?.name ?? t('fileAccepted');
  return <section className="profile-progress" aria-labelledby="profiling-title" aria-busy={loading}>
    <div className="profile-file"><span className="profile-file-icon"><FileText className="w-5 h-5" /></span><div><p className="section-eyebrow">{t('fileAccepted')}</p><h2 id="profiling-title">{fileName}</h2>{profile ? <p>{displayNumber(profile.row_count, language)} {t('rows')} · {profile.column_count} {t('columns')}</p> : <p>{t('uploadingFile')}</p>}</div></div>
    <div className="profile-stages" role="status" aria-live="polite">
      <Stage complete label={t('stageAccepted')} />
      <Stage complete={Boolean(profile?.row_count && profile.column_count)} busy={!profile} label={t('stageRecognized')} />
      <Stage complete={complete} busy={Boolean(profile) && loading} label={t('stageSchema')} />
      <Stage complete={complete && !loading} busy={Boolean(profile) && (!complete || loading)} label={t('stageExecutive')} />
    </div>
    <div className="profile-schema"><div><p className="section-eyebrow">{t('recognizedSchema')}</p><h3>{complete ? t('schemaReady') : t('schemaPreparing')}</h3></div>{schema.length ? <div className="schema-chips">{schema.map(column => <span key={column.name}>{column.name}<em>{column.kind}</em></span>)}</div> : <SkeletonLines count={3} />}</div>
    <div className="profile-skeletons" aria-label={t('executiveSkeletonLabel')}>
      <SkeletonCard /><SkeletonCard /><SkeletonCard />
    </div>
    <p className="profile-honesty">{t('profileHonesty')}</p>
  </section>;
}

function Stage({ complete, busy, label }: { complete: boolean; busy?: boolean; label: string }) { return <div className={complete ? 'done' : busy ? 'busy' : ''}>{complete ? <CheckCircle2 className="w-4 h-4" /> : busy ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <span className="stage-dot" />}<span>{label}</span></div>; }
function SkeletonLines({ count }: { count: number }) { return <div className="skeleton-lines">{Array.from({ length: count }, (_, index) => <span key={index} />)}</div>; }
function SkeletonCard() { return <div className="profile-skeleton-card" aria-hidden="true"><span /><span /><span /></div>; }
function PreviewCard({ icon, title, body }: { icon: ReactNode; title: string; body: string }) { return <article><span>{icon}</span><h3>{title}</h3><p>{body}</p></article>; }
