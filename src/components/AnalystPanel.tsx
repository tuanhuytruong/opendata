import { useEffect, useState } from 'react';
import { Check, Lightbulb, LoaderCircle, MessageSquareText, Pencil, ShieldCheck, SkipForward } from 'lucide-react';
import { AnalystPlan, AnalystProposal, ChartResult, DatasetProfile } from '../types';

interface Props { profile: DatasetProfile; onChart: (chart: ChartResult) => void; }
type ProposalState = 'ready' | 'loading' | 'approved' | 'skipped' | 'error';

export default function AnalystPanel({ profile, onChart }: Props) {
  const [plan, setPlan] = useState<AnalystPlan | null>(null);
  const [states, setStates] = useState<Record<string, ProposalState>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setPlan(null); setStates({}); setError(null);
    void fetch(`/api/runs/${profile.run_id}/analyst-proposals`).then(async (response) => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Could not prepare analyst proposals.');
      return result as AnalystPlan;
    }).then((result) => { if (active) setPlan(result); }).catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Could not prepare analyst proposals.'); });
    return () => { active = false; };
  }, [profile.run_id]);

  const approve = async (proposal: AnalystProposal) => {
    setStates((current) => ({ ...current, [proposal.id]: 'loading' }));
    try {
      const response = await fetch(`/api/runs/${profile.run_id}/chart`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(proposal.request) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'This chart proposal was rejected.');
      onChart(result as ChartResult);
      setStates((current) => ({ ...current, [proposal.id]: 'approved' }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not approve this proposal.');
      setStates((current) => ({ ...current, [proposal.id]: 'error' }));
    }
  };

  return <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
    <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:justify-between gap-4">
      <div><div className="flex items-center gap-2"><MessageSquareText className="w-5 h-5 text-indigo-600" /><h2 className="text-lg font-semibold">AI Analyst</h2></div><p className="text-sm text-slate-500 mt-1">Review suggested analyses, then explicitly approve the charts you want.</p></div>
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-full px-3 py-1.5 h-fit"><ShieldCheck className="w-3.5 h-3.5" /> Controlled analysis</span>
    </div>
    <div className="p-6">
      {!plan && !error && <div className="flex items-center gap-2 text-sm text-slate-500"><LoaderCircle className="w-4 h-4 animate-spin" /> Reading the dataset profile…</div>}
      {error && <p className="text-sm rounded-xl p-3 bg-rose-50 text-rose-700 border border-rose-100">{error}</p>}
      {plan && <><div className="rounded-xl bg-indigo-50 border border-indigo-100 p-4"><div className="flex gap-2"><Lightbulb className="w-4 h-4 text-indigo-600 mt-0.5 shrink-0" /><div><p className="text-sm font-medium text-indigo-950">Analysis brief</p><p className="text-sm text-indigo-800 mt-1">{plan.summary}</p></div></div></div>
        <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-4">{plan.proposals.map((proposal) => <ProposalCard key={proposal.id} proposal={proposal} state={states[proposal.id] ?? 'ready'} onApprove={() => void approve(proposal)} onSkip={() => setStates((current) => ({ ...current, [proposal.id]: 'skipped' }))} />)}</div>
        {!plan.proposals.length && <p className="text-sm text-slate-500">No safe metric/dimension pairing was found. Use the chart builder below to choose fields manually.</p>}
        <p className="mt-5 text-xs text-slate-500 border-t border-slate-100 pt-4">{plan.guardrail}</p>
      </>}
    </div>
  </section>;
}

function ProposalCard({ proposal, state, onApprove, onSkip }: { proposal: AnalystProposal; state: ProposalState; onApprove: () => void; onSkip: () => void }) {
  if (state === 'skipped') return <article className="border border-slate-100 rounded-xl p-4 opacity-55"><p className="text-sm text-slate-500">Skipped: {proposal.title}</p></article>;
  const done = state === 'approved';
  return <article className="border border-slate-200 rounded-xl p-4"><div className="flex justify-between gap-3"><div><h3 className="font-semibold text-sm text-slate-800">{proposal.title}</h3><p className="text-xs text-slate-500 mt-1">{proposal.request.chart_type} · sum of {proposal.request.metric} by {proposal.request.dimension}</p></div><span className="text-[10px] h-fit uppercase tracking-wide font-semibold px-2 py-1 rounded bg-slate-100 text-slate-500">Profile-based</span></div><p className="text-sm text-slate-600 mt-3">{proposal.rationale}</p><div className="flex gap-2 mt-4">{done ? <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700"><Check className="w-4 h-4" /> Added to chart plan</span> : <><button type="button" disabled={state === 'loading'} onClick={onApprove} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60">{state === 'loading' ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Approve</button><button type="button" onClick={onSkip} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"><SkipForward className="w-4 h-4" /> Skip</button><span className="inline-flex items-center text-xs text-slate-400"><Pencil className="w-3.5 h-3.5 mr-1" /> Edit below</span></>}</div></article>;
}
