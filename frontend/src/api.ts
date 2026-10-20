import type { Block, Health, JsonValue, Match, Mission, MissionStatus, Profile, ProfileInput, Recommendations, Report, Resource } from './types';

export class ApiError extends Error {
  code: string;
  constructor(message: string, code = 'request_failed') { super(message); this.code = code; }
}
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } }); }
  catch { throw new ApiError('PeerBridge could not reach the local server. Check that the Python backend is running.'); }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const details = Array.isArray(data?.error?.details) ? data.error.details.map((item: { field?: string; message?: string }) => `${(item.field || '').replace(/^body\./, '')}: ${item.message || 'Check this value'}`).join(' · ') : '';
    throw new ApiError(`${data?.error?.message || (typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status}).`)}${details ? ` ${details}` : ''}`, data?.error?.code);
  }
  return data as T;
}
const body = (value: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(value) });
export const api = {
  health: () => request<Health>('/health'),
  profiles: () => request<Profile[]>('/profiles'),
  saveProfile: (value: ProfileInput, id?: string) => request<Profile>(id ? `/profiles/${id}` : '/profiles', { ...body(value), method: id ? 'PUT' : 'POST' }),
  missions: () => request<Mission[]>('/missions'),
  ownMissions: (id: string) => request<Mission[]>(`/profiles/${id}/missions`),
  createMission: (requester_id: string, text: string) => request<Mission>('/missions', body({ requester_id, text })),
  updateMission: (id: string, status: MissionStatus) => request<Mission>(`/missions/${id}`, { ...body({ status }), method: 'PATCH' }),
  recommendations: (id: string) => request<Recommendations>(`/missions/${id}/recommendations`, body({})),
  matches: () => request<Match[]>('/matches'),
  accept: (mission_id: string, mentor_id: string) => request<Match>('/matches', body({ mission_id, mentor_id })),
  resources: () => request<Resource[]>('/resources'),
  reports: () => request<Report[]>('/reports'),
  report: (reporter_id: string, target_type: string, target_id: string, reason: string) => request<Report>('/reports', body({ reporter_id, target_type, target_id, reason })),
  blocks: (id: string) => request<Block[]>(`/blocks?profile_id=${encodeURIComponent(id)}`),
  block: (blocker_id: string, blocked_id: string) => request<Block>('/blocks', body({ blocker_id, blocked_id })),
  unblock: (id: string) => request<unknown>(`/blocks/${id}`, { method: 'DELETE' }),
  metrics: () => request<JsonValue>('/metrics'),
  batch: (dry_run: boolean) => request<JsonValue>('/assignments/batch', body({ dry_run })),
  reset: () => request<unknown>('/demo/reset', body({ confirm: true })),
};
