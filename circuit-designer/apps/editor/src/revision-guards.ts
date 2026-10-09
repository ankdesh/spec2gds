/** Pure revision decisions shared by browser behaviour and local tests. */
export interface ViewIdentity { epoch: number; key: string | null; request: number }

export function acceptsView(response: ViewIdentity, current: ViewIdentity): boolean {
  return response.request === current.request && response.epoch === current.epoch && response.key === current.key;
}

export function saveBaseRevision(reviewed: string | null, draft: string | null, source: string): string {
  return reviewed ?? draft ?? source;
}

export function draftRevisions(active: boolean, source: string): { draft: string | null; reviewed: null } {
  return { draft: active ? source : null, reviewed: null };
}
