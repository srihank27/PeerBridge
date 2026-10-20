export type Topic = 'algebra' | 'geometry' | 'python' | 'robotics' | 'writing' | 'presentations' | 'science' | 'physics' | 'study_skills' | 'school_transition';
export type Route = 'academic' | 'school_transition' | 'clarify' | 'private_support';
export type MissionStatus = 'open' | 'matched' | 'completed' | 'cancelled' | 'private';
export interface Profile {
  id: string; alias: string; avatar_id: string; grade_band: string; strengths: Topic[]; needs: Topic[];
  available_slots: string[]; capacity: number; support_preferences: string[]; active_matches: number; remaining_capacity: number;
}
export type ProfileInput = Omit<Profile, 'id' | 'active_matches' | 'remaining_capacity'>;
export interface Analysis { method: string; confidence: number; uncertainty: number; reason: string }
export interface Mission { id: string; requester_id: string; requester_alias: string; text: string; topic: Topic | null; route: Route; status: MissionStatus; created_at: string; analysis: Analysis }
export interface Scores { S: number; A: number; C: number; F: number }
export interface Resource { id: string; title: string; url: string; topics: Topic[]; access_notes: string; verified_at: string }
export interface Candidate { mentor: Profile; score: number; component_scores: Scores; explanation: string; shared_slots: string[] }
export interface Recommendations { route: Route; topic: Topic | null; analysis: Analysis; matching_mode: string; fallback_reason: string | null; threshold: number; candidates: Candidate[]; resources: Resource[]; support_message: string | null }
export interface Match { id: string; mission_id: string; mentor_id: string; requester_id: string; mentor_alias: string; requester_alias: string; topic: Topic; component_scores: Scores; score: number; explanation: string; status: string; created_at: string }
export interface Health { status: string; matching_mode: string; model_name: string; fallback_reason: string | null; demo: boolean }
export interface Block { id: string; blocker_id: string; blocked_id: string }
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export interface Report { id: string; target_type: string; target_id: string; reason: string; review_status: string; created_at?: string; [key: string]: unknown }
