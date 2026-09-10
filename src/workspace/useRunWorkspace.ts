import { useCallback, useEffect, useRef, useState } from 'react';

import { DatasetProfile, EDAResult, ExecutiveOverview, StarterView, CustomReportDocument, DateScope } from '../types';
import { Language } from '../i18n';

export type WorkspaceResources = {
  starterViews: StarterView[];
  overview: ExecutiveOverview | null;
  eda: EDAResult | null;
  report: CustomReportDocument | null;
  refreshing: boolean;
  error: string | null;
};

const emptyResources: WorkspaceResources = { starterViews: [], overview: null, eda: null, report: null, refreshing: false, error: null };

/** Owns run bootstrap and global-scope refresh. Older results stay visible on transient errors. */
export function useRunWorkspace(profile: DatasetProfile | null, language: Language, dateScope: DateScope | null) {
  const [resources, setResources] = useState<WorkspaceResources>(emptyResources);
  const overviewSequence = useRef(0);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (!profile || profile.profile_status !== 'complete') return;
    const sequence = ++overviewSequence.current;
    const scopeParams = dateScope ? `&date_column=${encodeURIComponent(dateScope.column)}${dateScope.start ? `&start=${encodeURIComponent(dateScope.start)}` : ''}${dateScope.end ? `&end=${encodeURIComponent(dateScope.end)}` : ''}` : '';
    setResources(current => ({ ...current, refreshing: true, error: null }));
    try {
      const response = await fetch(`/api/runs/${profile.run_id}/executive-overview?language=${language}${scopeParams}`, { signal });
      if (!response.ok) throw new Error(`Refresh failed (${response.status}).`);
      const overview = await response.json() as ExecutiveOverview;
      if (!signal?.aborted && sequence === overviewSequence.current) setResources(current => ({ ...current, overview, refreshing: false }));
    } catch (error) {
      if (!signal?.aborted && sequence === overviewSequence.current) setResources(current => ({ ...current, refreshing: false, error: error instanceof Error ? error.message : 'Unable to refresh the current scope.' }));
    }
  }, [profile?.run_id, profile?.profile_status, language, dateScope?.column, dateScope?.start, dateScope?.end]);

  useEffect(() => {
    if (!profile || profile.profile_status !== 'complete') { setResources(emptyResources); return; }
    const controller = new AbortController();
    const json = async <T,>(path: string): Promise<T> => { const response = await fetch(path, { signal: controller.signal }); if (!response.ok) throw new Error(`Workspace setup failed (${response.status}).`); return response.json() as Promise<T>; };
    Promise.all([json<{ proposals: StarterView[] }>(`/api/runs/${profile.run_id}/starter-views?language=${language}`), json<EDAResult>(`/api/runs/${profile.run_id}/eda`), json<CustomReportDocument>(`/api/runs/${profile.run_id}/custom-report`)]).then(([views, eda, report]) => { if (!controller.signal.aborted) setResources(current => ({ ...current, starterViews: views.proposals ?? [], eda, report, error: null })); }).catch(error => { if (!controller.signal.aborted) setResources(current => ({ ...current, error: error instanceof Error ? error.message : 'Unable to prepare workspace.' })); });
    return () => controller.abort();
  }, [profile?.run_id, profile?.profile_status, language]);

  useEffect(() => { const controller = new AbortController(); void refresh(controller.signal); return () => controller.abort(); }, [refresh]);
  return { ...resources, refresh, setReport: (report: CustomReportDocument | null) => setResources(current => ({ ...current, report })) };
}
