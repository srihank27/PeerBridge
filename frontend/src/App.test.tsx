import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, configure, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import type { Match, Mission, Profile, ProfileInput } from './types';

// These are DOM/API integration tests against the real local FastAPI service.
// They intentionally mutate and reset its dedicated QA database, never mock API data.
const origin = process.env.PEERBRIDGE_TEST_URL;
let verifiedQa = false;
const realFetch = globalThis.fetch.bind(globalThis);
configure({ asyncUtilTimeout: 12_000 });

async function server<T>(path: string, value?: unknown, method = 'POST'): Promise<T> {
  if (!origin) throw new Error('PEERBRIDGE_TEST_URL must explicitly identify an isolated QA server. Use scripts/test_frontend.py.');
  const response = await realFetch(`${origin}/api${path}`, value === undefined ? undefined : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  return data as T;
}
async function createProfile(alias: string, values: Partial<ProfileInput> = {}) {
  return server<Profile>('/profiles', { alias, avatar_id: 'bolt', grade_band: 'high', strengths: ['presentations'], needs: ['algebra'], available_slots: ['Tue 16:00'], support_preferences: ['step_by_step'], capacity: 2, ...values });
}
async function showApp(identity?: string) {
  if (identity) localStorage.setItem('peerbridge.demo-profile', identity);
  render(<App />);
  await screen.findByRole('heading', { name: /Hey,/ });
  return userEvent.setup();
}
function identitySelect() { return screen.getByRole('combobox', { name: 'Switch or manage fictional demo identity' }); }
async function postMission(user: ReturnType<typeof userEvent.setup>, text: string) {
  await user.click(screen.getByRole('button', { name: 'Post a mission' }));
  await user.type(screen.getByRole('textbox', { name: 'Tell us what you need help with' }), text);
  await user.click(screen.getByRole('button', { name: 'Find my next step' }));
}

beforeAll(async () => {
  if (!origin) throw new Error('PEERBRIDGE_TEST_URL is required. Run scripts/test_frontend.py to launch an isolated QA server.');
  const health = await server<{ demo: boolean; qa_mode: boolean }>('/health');
  if (!health.demo || health.qa_mode !== true) throw new Error('Integration tests require a verified QA server with PEERBRIDGE_TEST_MODE=1. No demo data was reset.');
  verifiedQa = true;
  vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) => realFetch(typeof input === 'string' && input.startsWith('/') ? `${origin}${input}` : input, init));
});
beforeEach(async () => { if (!verifiedQa) throw new Error('QA server verification is required before resetting data.'); cleanup(); localStorage.clear(); await server('/demo/reset', { confirm: true }); });
afterEach(() => cleanup());
afterAll(async () => { try { if (verifiedQa) await server('/demo/reset', { confirm: true }); } finally { vi.unstubAllGlobals(); } });

describe('PeerBridge real-backend DOM journeys', () => {
  it('creates and edits a persistent hero with multiple strengths, needs, slots, and preferences', async () => {
    const user = await showApp();
    await user.selectOptions(identitySelect(), '__new__');
    const dialog = screen.getByRole('dialog', { name: 'Every hero starts somewhere.' });
    await user.type(within(dialog).getByRole('textbox', { name: 'Hero alias' }), 'IntegrationHero');
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Grade band' }), 'high');
    const strengths = within(dialog).getByRole('group', { name: 'I can help with' });
    await user.click(within(strengths).getByRole('checkbox', { name: 'Python' }));
    await user.click(within(strengths).getByRole('checkbox', { name: 'Robotics' }));
    const needs = within(dialog).getByRole('group', { name: 'I would like help with' });
    await user.click(within(needs).getByRole('checkbox', { name: 'Writing' }));
    await user.click(within(needs).getByRole('checkbox', { name: 'Presentations' }));
    await user.click(within(dialog).getByRole('checkbox', { name: 'Tue 4 pm' }));
    await user.click(within(dialog).getByRole('checkbox', { name: 'Thu 4 pm' }));
    await user.click(within(dialog).getByRole('checkbox', { name: 'Practice together' }));
    await user.click(within(dialog).getByRole('button', { name: 'Create hero profile' }));
    await screen.findByRole('heading', { name: 'Hey, IntegrationHero✦' });
    const saved = (await server<Profile[]>('/profiles')).find(p => p.alias === 'IntegrationHero')!;
    expect(saved.strengths).toEqual(['python', 'robotics']);
    expect(saved.needs).toEqual(['writing', 'presentations']);
    expect(saved.available_slots).toEqual(['Tue 16:00', 'Thu 16:00']);
    expect(saved.support_preferences).toEqual(['step_by_step', 'practice']);
    expect((identitySelect() as HTMLSelectElement).value).toBe(saved.id);
    await user.selectOptions(identitySelect(), '__edit__');
    const edit = screen.getByRole('dialog', { name: 'Edit your hero profile' });
    await user.clear(within(edit).getByRole('spinbutton', { name: /Mentor capacity/ }));
    await user.type(within(edit).getByRole('spinbutton', { name: /Mentor capacity/ }), '3');
    await user.click(within(edit).getByRole('button', { name: 'Save hero profile' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect((await server<Profile[]>('/profiles')).find(p => p.id === saved.id)?.capacity).toBe(3);
  });

  it('posts a public mission, explains and confirms a real match, enforces capacity, and releases it on completion', async () => {
    const mentor = await createProfile('IntegrationMentor', { strengths: ['algebra'], needs: [], capacity: 1 });
    const requester = await createProfile('IntegrationLearner');
    const user = await showApp(requester.id);
    const text = 'I need algebra help solving linear equations with letters for a new classroom exercise.';
    await postMission(user, text);
    await screen.findByRole('heading', { name: 'IntegrationMentor' });
    const candidate = screen.getByRole('heading', { name: 'IntegrationMentor' }).closest('article')!;
    expect(within(candidate).getByText('Topic relevance')).toBeTruthy();
    expect(within(candidate).getByText('Availability overlap')).toBeTruthy();
    expect(within(candidate).getByText('Support preference')).toBeTruthy();
    expect(within(candidate).getByText('Remaining capacity')).toBeTruthy();
    expect(within(candidate).getByText('Tue 16:00')).toBeTruthy();
    await user.click(within(candidate).getByRole('button', { name: 'Confirm team-up' }));
    await screen.findByRole('heading', { name: 'This mission has a confirmed teammate.' });
    const assignments = await server<Match[]>('/matches');
    const match = assignments.find(m => m.mentor_id === mentor.id && m.requester_id === requester.id)!;
    expect(match.status).toBe('active');
    expect((await server<Profile[]>('/profiles')).find(p => p.id === mentor.id)?.remaining_capacity).toBe(0);
    await user.click(screen.getByRole('button', { name: 'Close dialog' }));
    await user.selectOptions(identitySelect(), mentor.id);
    await screen.findByRole('heading', { name: 'Hey, IntegrationMentor✦' });
    await user.click(screen.getByRole('button', { name: 'Give & get' }));
    await screen.findByText('IntegrationLearner', { selector: '.match-body strong' });
    await user.selectOptions(identitySelect(), requester.id);
    await screen.findByRole('button', { name: text });
    await user.click(screen.getByRole('button', { name: 'Complete', exact: true }));
    await waitFor(async () => expect((await server<Profile[]>('/profiles')).find(p => p.id === mentor.id)?.remaining_capacity).toBe(1));
    expect((await server<Match[]>('/matches')).find(m => m.id === match.id)?.status).toBe('completed');
    expect(screen.getByRole('button', { name: 'Reopen' })).toBeTruthy();
  });

  it('keeps sensitive and ambiguous requests off the public board and shows honest support states', async () => {
    const requester = await createProfile('RoutingLearner');
    const user = await showApp(requester.id);
    const privateText = 'I am being bullied and do not feel safe at school after an incident today.';
    await postMission(user, privateText);
    await screen.findByRole('heading', { name: 'You deserve support.' });
    await screen.findByRole('heading', { name: 'You don’t have to figure this out alone.' });
    expect(screen.getByText(/No adult has been contacted\. No live staff member monitors this demo\./)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Confirm team-up' })).toBeNull();
    expect((await server<Mission[]>('/missions')).some(m => m.text === privateText)).toBe(false);
    await user.click(screen.getByRole('button', { name: 'Close dialog' }));
    const unclearText = 'Can you help with my confusing situation please?';
    await postMission(user, unclearText);
    await screen.findByRole('heading', { name: 'A little more detail will help.' });
    await screen.findByRole('button', { name: 'Write a clearer request' });
    expect(screen.queryByRole('button', { name: 'Confirm team-up' })).toBeNull();
    expect((await server<Mission[]>('/missions')).some(m => m.text === unclearText)).toBe(false);
    const owned = await server<Mission[]>(`/profiles/${requester.id}/missions`);
    expect(owned.find(m => m.text === privateText)?.route).toBe('private_support');
    expect(owned.find(m => m.text === unclearText)?.route).toBe('clarify');
  });

  it('displays duplicate and contact-detail errors without publishing another mission', async () => {
    const requester = await createProfile('ValidationLearner');
    const text = 'I need algebra practice solving equations for an extra classroom worksheet.';
    await server('/missions', { requester_id: requester.id, text });
    const user = await showApp(requester.id);
    await postMission(user, text);
    expect((await screen.findByRole('alert')).textContent).toContain('already have this mission');
    const field = screen.getByRole('textbox', { name: 'Tell us what you need help with' });
    await user.clear(field);
    await user.type(field, 'I need algebra help. Email fictional@example.com to arrange a meeting.');
    await user.click(screen.getByRole('button', { name: 'Find my next step' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Remove contact details'));
    expect((await server<Mission[]>(`/profiles/${requester.id}/missions`)).filter(m => m.text === text)).toHaveLength(1);
    expect((await server<Mission[]>('/missions')).some(m => m.text.includes('fictional@example.com'))).toBe(false);
  });

  it('records a redacted report, blocks the pairing, and renders the simulated review queue', async () => {
    const user = await showApp('learner-aria');
    await user.click(screen.getByRole('button', { name: /Mission board/ }));
    await user.click(screen.getAllByRole('button', { name: 'Report mission by MoonTrail' })[0]);
    const dialog = screen.getByRole('dialog', { name: 'Raise a shield' });
    const reason = 'A fictional demo concern that should stay redacted in the review queue.';
    await user.type(within(dialog).getByRole('textbox', { name: 'Reason' }), reason);
    await user.click(within(dialog).getByRole('checkbox', { name: /Also block this hero/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Record demo report' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    const reports = await server<{ reason: string; review_status: string }[]>('/reports');
    expect(reports).toHaveLength(1);
    expect(reports[0].review_status).toBe('simulated_pending');
    expect(reports[0].reason).not.toBe(reason);
    expect(await server<unknown[]>('/blocks?profile_id=learner-aria')).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Demo lab' }));
    await screen.findByText('Simulated pending');
    expect(screen.getByText(/No adult is contacted\. No live staff member monitors this queue/)).toBeTruthy();
    expect(screen.queryByText(reason)).toBeNull();
  });

  it('retrieves resources, renders measured evaluation tables, previews and confirms batch assignment, then resets', async () => {
    const user = await showApp();
    await user.click(screen.getByRole('button', { name: 'Resource Vault' }));
    await screen.findByRole('heading', { name: 'The Resource Vault' });
    expect(screen.getAllByRole('link', { name: /Open resource/ }).length).toBeGreaterThanOrEqual(8);
    expect(screen.getAllByText('Verified 2026-10-19').length).toBeGreaterThanOrEqual(8);
    await user.click(screen.getByRole('button', { name: 'Geometry', exact: true }));
    expect(screen.getAllByRole('link', { name: /Open resource/ })).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'School transition', exact: true }));
    expect(screen.getByText('No verified directory link for this topic')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Demo lab' }));
    await user.click(screen.getByRole('button', { name: 'Run evaluation' }));
    const comparison = await screen.findByRole('table', { name: 'Recommendation comparison' });
    expect(within(comparison).getByRole('rowheader', { name: 'Keyword' })).toBeTruthy();
    expect(within(comparison).getByRole('rowheader', { name: 'Semantic' })).toBeTruthy();
    const engine = await server<{ matching_mode: string }>('/health');
    if (engine.matching_mode === 'semantic') expect(within(comparison).queryByText(/Not run\./)).toBeNull();
    else expect(within(comparison).getByText(/Not run\./)).toBeTruthy();
    expect(screen.getByRole('table', { name: 'Assignment simulation' })).toBeTruthy();
    expect((await server<Match[]>('/matches')).filter(m => m.status === 'active')).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Preview assignments' }));
    await screen.findByRole('button', { name: 'Confirm demo assignments' });
    expect((await server<Match[]>('/matches')).filter(m => m.status === 'active')).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Confirm demo assignments' }));
    await waitFor(async () => expect((await server<Match[]>('/matches')).filter(m => m.status === 'active').length).toBeGreaterThan(1));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Confirm demo assignments' })).toBeNull());
    await user.click(screen.getByRole('button', { name: 'Reset demo' }));
    expect(screen.getByRole('dialog', { name: 'Restore the fictional network?' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Keep exploring' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Reset demo' }));
    await user.click(screen.getByRole('button', { name: 'Reset fictional demo' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect((await server<Match[]>('/matches')).filter(m => m.status === 'active')).toHaveLength(1);
  });
});
