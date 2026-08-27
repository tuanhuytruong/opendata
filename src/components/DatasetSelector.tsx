import React, { useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Database, FileSpreadsheet, LoaderCircle, Upload } from 'lucide-react';
import { DatasetProfile } from '../types';

interface DatasetSelectorProps {
  profile: DatasetProfile | null;
  onProfile: (profile: DatasetProfile) => void;
}

export default function DatasetSelector({ profile, onProfile }: DatasetSelectorProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const upload = async (file: File) => {
    if (!/\.(csv|xlsx)$/i.test(file.name)) {
      setError('Upload a CSV or XLSX file. Legacy XLS is not supported.');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const response = await fetch('/api/runs/upload', { method: 'POST', body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The profiling service rejected this file.');
      onProfile(result as DatasetProfile);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed. Check that the report API is running.');
    } finally {
      setUploading(false);
    }
  };

  return <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
    <div className="flex items-center justify-between gap-3 mb-3">
      <div className="flex items-center gap-2"><Database className="w-5 h-5 text-indigo-600" /><h2 className="text-lg font-semibold text-slate-800">1. Select data</h2></div>
      <span className="text-xs font-mono px-2.5 py-1 bg-slate-50 text-slate-500 rounded-full border border-slate-200">This machine</span>
    </div>
    <p className="text-sm text-slate-500 mb-5">Upload a CSV or XLSX for a server-side, read-only profile. Browser data is not sent to an AI model.</p>
    <div onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragActive(false)} onDrop={(event) => { event.preventDefault(); setDragActive(false); const file = event.dataTransfer.files[0]; if (file) void upload(file); }} onClick={() => inputRef.current?.click()} className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 bg-slate-50/50 hover:border-slate-300'}`}>
      <input ref={inputRef} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} />
      {uploading ? <LoaderCircle className="w-8 h-8 text-indigo-600 mx-auto mb-2 animate-spin" /> : <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />}
      <p className="text-sm font-medium text-slate-700">{uploading ? 'Profiling your dataset…' : <>Drag & drop a CSV, or <span className="text-indigo-600 underline">browse</span></>}</p>
      <p className="text-xs text-slate-400 mt-1">Up to 50 MB / 200,000 rows for the first release</p>
    </div>
    {error && <div className="flex gap-2 p-3 mt-4 bg-rose-50 border border-rose-100 text-rose-700 rounded-xl text-xs"><AlertCircle className="w-4 h-4 shrink-0" />{error}</div>}
    {profile && <div className="flex gap-2 p-3 mt-4 bg-emerald-50 border border-emerald-100 text-emerald-800 rounded-xl text-xs"><CheckCircle2 className="w-4 h-4 shrink-0" /><span><strong>{profile.file_name}</strong> · {profile.row_count.toLocaleString()} rows · {profile.column_count} columns</span></div>}
  </section>;
}
