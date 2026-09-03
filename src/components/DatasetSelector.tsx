import React, { useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Database, LoaderCircle, Upload } from 'lucide-react';
import { DatasetProfile } from '../types';
import { Language, text } from '../i18n';

interface DatasetSelectorProps {
  profile: DatasetProfile | null;
  language: Language;
  onProfile: (profile: DatasetProfile) => void;
}

export default function DatasetSelector({ profile, language, onProfile }: DatasetSelectorProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const upload = async (file: File) => {
    if (!/\.(csv|xlsx)$/i.test(file.name)) { setError(text(language, 'uploadInvalid')); return; }
    setUploading(true); setError(null);
    try {
      const form = new FormData(); form.append('file', file);
      const response = await fetch('/api/runs/upload', { method: 'POST', body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The profiling service rejected this file.');
      onProfile(result as DatasetProfile);
    } catch (err) { setError(err instanceof Error ? err.message : 'Upload failed. Check that the report API is running.'); }
    finally { setUploading(false); }
  };

  return <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
    <div className="flex items-center gap-2 mb-3"><span className="grid place-items-center h-9 w-9 rounded-lg bg-indigo-50 text-indigo-600"><Database className="w-5 h-5" /></span><div><h2 className="text-lg font-semibold text-slate-800">{text(language, 'upload')}</h2><p className="text-xs text-slate-500">{text(language, 'uploadHint')}</p></div></div>
    <div onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragActive(false)} onDrop={(event) => { event.preventDefault(); setDragActive(false); const file = event.dataTransfer.files[0]; if (file) void upload(file); }} onClick={() => inputRef.current?.click()} className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 bg-slate-50/50 hover:border-indigo-300'}`}>
      <input ref={inputRef} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} />
      {uploading ? <LoaderCircle className="w-8 h-8 text-indigo-600 mx-auto mb-3 animate-spin" /> : <Upload className="w-8 h-8 text-slate-400 mx-auto mb-3" />}
      <p className="text-sm font-medium text-slate-700">{uploading ? text(language, 'profilePreparing') : <>Drag & drop a CSV, or <span className="text-indigo-600 underline">browse</span></>}</p>
      <p className="text-xs text-slate-400 mt-1">100 MB · 600,000 rows</p>
    </div>
    {error && <div className="flex gap-2 p-3 mt-4 bg-rose-50 border border-rose-100 text-rose-700 rounded-xl text-xs"><AlertCircle className="w-4 h-4 shrink-0" />{error}</div>}
    {profile && <div className="flex gap-2 p-3 mt-4 bg-emerald-50 border border-emerald-100 text-emerald-800 rounded-xl text-xs"><CheckCircle2 className="w-4 h-4 shrink-0" /><span><strong>{profile.file_name}</strong> · {profile.row_count.toLocaleString()} {text(language, 'rows')} · {profile.column_count} {text(language, 'columns')}</span></div>}
  </section>;
}
