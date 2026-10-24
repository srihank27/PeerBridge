import { useState, type FormEvent } from 'react';
import { api } from './api';
import { setTopicCatalog, useTopics } from './topics';
import type { SupportedTopic } from './types';

export function TopicManager() {
  const topics = useTopics();
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [keywords, setKeywords] = useState('');
  const [description, setDescription] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  function reset() { setEditing(null); setName(''); setKeywords(''); setDescription(''); setError(''); }
  function edit(topic: SupportedTopic) {
    setEditing(topic.id); setName(topic.label); setKeywords(topic.keywords.join(', ')); setDescription(topic.description); setError(''); setNotice('');
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setPending(true); setError(''); setNotice('');
    try {
      const result = await api.saveTopic({ label: name.trim(), keywords: keywords.split(',').map(word => word.trim()).filter(Boolean), description: description.trim() }, editing || undefined);
      setTopicCatalog(await api.topics()); reset();
      setNotice(`${result.label} saved. It is now available in profiles and mission filters. New requests will use its keywords and description.`);
    } catch (error) { setError((error as Error).message); }
    finally { setPending(false); }
  }
  return <>
    <div className="page-heading"><div><span className="eyebrow">GROW THE NETWORK</span><h1>Manage topics</h1><p>Add subjects your community can help with, or improve how existing subjects are recognized.</p></div></div>
    <div className="notice"><p>Topic changes apply to this shared fictional demo. Add the topic to a mentor?s strengths to enable matching. Previously unclear requests need to be submitted again.</p></div>
    <div className="topic-manager-layout">
      <section className="panel topic-editor" aria-label="Topic editor"><h2>{editing ? 'Edit topic' : 'Add a topic'}</h2>
        <form className="stack-form" onSubmit={save}>
          <label>Topic name<input value={name} onChange={event => setName(event.target.value)} required minLength={2} maxLength={60} placeholder="Calculus" /></label>
          <label>Keywords<textarea aria-label="Keywords" value={keywords} onChange={event => setKeywords(event.target.value)} required rows={3} placeholder="calculus, derivative, derivatives, integral, chain rule" /><small>Separate words or phrases with commas. Use up to 40 distinct keywords.</small></label>
          <label>Semantic description<textarea aria-label="Semantic description" value={description} onChange={event => setDescription(event.target.value)} required minLength={8} maxLength={600} rows={4} placeholder="Calculus: limits, derivatives, integration, rates of change, and areas under curves." /><small>Describe the subject to help semantic matching recognize related requests.</small></label>
          {error && <div className="error-banner" role="alert">{error}</div>}
          <div className="modal-actions">{editing && <button type="button" className="button button-ghost" disabled={pending} onClick={reset}>Cancel editing</button>}<button className="button button-primary" disabled={pending}>{pending ? 'Saving topic?' : editing ? 'Save topic' : 'Add topic'}</button></div>
        </form>
      </section>
      <section className="panel topic-catalog" aria-label="Supported topics"><h2>Supported topics ({topics.length})</h2><p className="muted">Edit names, keywords, and descriptions. Saved topic IDs stay fixed to preserve existing profiles and requests.</p>
        {topics.map(topic => <article className="topic-catalog-item" key={topic.id}><div><h3>{topic.label}</h3><p>{topic.description}</p><small>Keywords: {topic.keywords.join(', ')}</small></div><button className="text-button" aria-label={`Edit ${topic.label}`} disabled={pending} onClick={() => edit(topic)}>Edit</button></article>)}
      </section>
    </div>
    {notice && <div role="status" className="notice">{notice}</div>}
  </>;
}
