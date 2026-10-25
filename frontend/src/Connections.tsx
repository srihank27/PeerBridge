import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Clock3, HeartHandshake, Users } from 'lucide-react';
import type { Match, Profile } from './types';
import { Avatar, Badge, Empty, date, label } from './ui';

interface CardProps {
  match: Match;
  viewerId: string;
  profiles: Profile[];
  selected?: boolean;
  onView?: () => void;
}

export function TeammateCard({ match, viewerId, profiles, selected, onView }: CardProps) {
  const card = useRef<HTMLElement>(null);
  const giving = match.mentor_id === viewerId;
  const participating = giving || match.requester_id === viewerId;
  const counterpartId = giving ? match.requester_id : match.mentor_id;
  const counterpart = profiles.find(profile => profile.id === counterpartId);
  const alias = giving ? match.requester_alias : match.mentor_alias;
  const mentor = profiles.find(profile => profile.id === match.mentor_id);
  const requester = profiles.find(profile => profile.id === match.requester_id);
  const sharedSlots = mentor && requester ? mentor.available_slots.filter(slot => requester.available_slots.includes(slot)) : [];
  useEffect(() => {
    if (selected) {
      card.current?.focus({ preventScroll: true });
      card.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selected]);
  return <article ref={card} tabIndex={-1} id={`connection-${match.id}`} aria-label={`Connection with ${alias}`} className={`teammate-card${selected ? ' teammate-card-selected' : ''}`}>
    <div className="teammate-card-header">
      <Avatar variant={counterpart?.avatar_id} />
      <div className="teammate-card-person"><span>{participating ? giving ? 'You?re helping' : 'Helping you' : 'Confirmed mentor'}</span><h3>{alias}</h3><small>{counterpart ? counterpart.grade_band === 'middle' ? 'Middle school' : 'High school' : 'Fictional hero'} ? Demo identity</small></div>
      <Badge tone={match.status === 'active' ? 'green' : 'neutral'}>{label(match.status)}</Badge>
    </div>
    <div className="teammate-card-subject"><HeartHandshake size={17} aria-hidden="true" /><span>{label(match.topic)} ? {match.mentor_alias} helping {match.requester_alias}</span></div>
    <div className="teammate-card-strengths"><strong>{giving ? 'Your relevant strength' : 'Relevant mentor strength'}</strong><div className="tag-row">{mentor?.strengths.includes(match.topic) ? <span className="topic-tag">{label(match.topic)}</span> : <span className="muted">No current strength declared for this subject.</span>}</div></div>
    <div className="teammate-card-availability"><strong><Clock3 size={15} aria-hidden="true" /> Current shared availability</strong><p>{sharedSlots.length ? sharedSlots.join(' ? ') : 'No shared slots currently listed.'}</p><small>Shared availability is not a booked session.</small></div>
    <div className="teammate-card-footer"><small>Connected {date(match.created_at)}</small>{onView && participating && <button className="button button-primary button-small" onClick={onView}>View connection <ArrowRight size={15} /></button>}</div>
  </article>;
}

interface PageProps {
  me: Profile;
  matches: Match[];
  profiles: Profile[];
  selectedId: string | null;
  onExplore: () => void;
  onAsk: () => void;
  onRequests: () => void;
}

export function MyConnections({ me, matches, profiles, selectedId, onExplore, onAsk, onRequests }: PageProps) {
  const [filter, setFilter] = useState<'active' | 'past' | 'all'>('active');
  const ownMatches = matches.filter(match => match.mentor_id === me.id || match.requester_id === me.id);
  const active = ownMatches.filter(match => match.status === 'active');
  const past = ownMatches.filter(match => match.status !== 'active');
  const visible = filter === 'active' ? active : filter === 'past' ? past : ownMatches;
  const helpingYou = visible.filter(match => match.requester_id === me.id);
  const helpingOthers = visible.filter(match => match.mentor_id === me.id);
  const cards = (items: Match[]) => <div className="connections-grid">{items.map(match => <TeammateCard key={match.id} match={match} profiles={profiles} viewerId={me.id} selected={selectedId === match.id} />)}</div>;
  return <>
    <div className="page-heading"><div><span className="eyebrow">YOUR PEOPLE. YOUR NEXT STEP.</span><h1>My connections</h1><p>{me.alias}?s confirmed team-ups. See who?s helping you and who you?re helping.</p></div><button className="button button-secondary" onClick={onRequests}>View your requests <ArrowRight size={16} /></button></div>
    <div className="connections-toolbar"><div className="topic-filters" role="group" aria-label="Filter connections">{(['active', 'past', 'all'] as const).map(value => <button key={value} aria-pressed={filter === value} className={filter === value ? 'selected' : ''} onClick={() => setFilter(value)}>{label(value)} ({value === 'active' ? active.length : value === 'past' ? past.length : ownMatches.length})</button>)}</div><span className="muted">{active.length} active {active.length === 1 ? 'connection' : 'connections'}</span></div>
    {visible.length ? <div className="connection-groups">
      {helpingYou.length > 0 && <section aria-label="People helping you"><div className="section-heading"><h2><HeartHandshake size={21} /> Helping you</h2><Badge>{helpingYou.length}</Badge></div>{cards(helpingYou)}</section>}
      {helpingOthers.length > 0 && <section aria-label="People you are helping"><div className="section-heading"><h2><Users size={21} /> You?re helping</h2><Badge>{helpingOthers.length}</Badge></div>{cards(helpingOthers)}</section>}
    </div> : <Empty title={filter === 'past' ? 'No past connections yet' : filter === 'all' ? 'Your team starts here' : 'No active connections yet'}>{filter === 'past' ? 'Completed and cancelled team-ups will appear here.' : 'Ask for help and confirm an eligible teammate, or explore requests where you could help.'}<div className="connection-empty-actions"><button className="button button-primary" onClick={onAsk}>Ask for help</button><button className="button button-secondary" onClick={onExplore}>Explore missions</button></div></Empty>}
  </>;
}
