"""Persistent topic configuration drives real validation and matching."""
import pytest
from fastapi.testclient import TestClient
from backend.peerbridge import db, semantic
from backend.peerbridge.analysis import analyze_text
from backend.peerbridge.main import app

CALCULUS = {
    'label': 'Calculus',
    'keywords': ['calculus', 'derivative', 'derivatives', 'integral', 'chain rule'],
    'description': 'Calculus limits derivatives integration rates of change and areas under curves.',
}

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('PEERBRIDGE_DB', str(tmp_path / 'topics.sqlite3'))
    monkeypatch.setenv('PEERBRIDGE_MATCHING', 'keyword')
    with TestClient(app) as client:
        yield client


def add_calculus(client):
    response = client.post('/api/topics', json=CALCULUS)
    assert response.status_code == 201, response.text
    return response.json()


def test_new_topic_drives_profile_validation_analysis_and_matching(client):
    topic = add_calculus(client)
    assert topic['id'] == 'calculus'
    body = dict(alias='CalcMentor', avatar_id='bolt', grade_band='high', strengths=['calculus'], needs=[], available_slots=['Tue 16:00'], support_preferences=['practice'], capacity=2)
    mentor = client.post('/api/profiles', json=body)
    assert mentor.status_code == 201, mentor.text
    requester = client.post('/api/profiles', json=dict(body, alias='CalcLearner', strengths=[], needs=['calculus'])).json()
    mission = client.post('/api/missions', json={'requester_id': requester['id'], 'text': 'I am working on Calculus and Need help.'})
    assert mission.status_code == 201, mission.text
    assert mission.json()['topic'] == 'calculus'
    assert mission.json()['route'] == 'academic'
    recommendations = client.post('/api/missions/' + mission.json()['id'] + '/recommendations').json()
    assert mentor.json()['id'] in [candidate['mentor']['id'] for candidate in recommendations['candidates']]
    accepted = client.post('/api/matches', json={'mission_id': mission.json()['id'], 'mentor_id': mentor.json()['id']})
    assert accepted.status_code == 201, accepted.text


def test_topic_changes_preserve_ids_and_survive_initialization_and_demo_reset(client):
    add_calculus(client)
    update = dict(CALCULUS, label='Advanced Calculus', keywords=['calculus', 'antiderivative'])
    response = client.put('/api/topics/calculus', json=update)
    assert response.status_code == 200
    assert response.json()['id'] == 'calculus'
    assert analyze_text('Please explain the antiderivative.')['topic'] == 'calculus'
    db.init_database()
    client.post('/api/demo/reset', json={'confirm': True})
    saved = next(t for t in client.get('/api/topics').json() if t['id'] == 'calculus')
    assert saved['label'] == 'Advanced Calculus'
    assert saved['keywords'] == update['keywords']


@pytest.mark.parametrize('changes', [
    {'label': 'all'}, {'label': 'Private Support'},
    {'keywords': []}, {'keywords': [' ']},
    {'keywords': ['Calculus', 'calculus']}, {'description': 'short'},
])
def test_invalid_topic_configuration_is_rejected(client, changes):
    assert client.post('/api/topics', json=dict(CALCULUS, **changes)).status_code == 422


def test_duplicate_topics_and_unknown_profile_topics_are_rejected(client):
    add_calculus(client)
    assert client.post('/api/topics', json=dict(CALCULUS, label='CALCULUS')).status_code == 409
    assert client.put('/api/topics/calculus', json=dict(CALCULUS, label='Algebra')).status_code == 409
    assert client.put('/api/topics/missing', json=CALCULUS).status_code == 404
    response = client.post('/api/profiles', json=dict(alias='InvalidTopic', avatar_id='bolt', grade_band='high', strengths=['imaginary_topic']))
    assert response.status_code == 422


def test_semantic_matching_uses_current_topic_descriptions(client, monkeypatch):
    import numpy as np
    add_calculus(client)
    seen = []
    def embed(text):
        seen.append(text)
        return np.array([1.0, 0.0])
    monkeypatch.setattr(semantic, 'effective_mode', lambda mode=None: 'semantic')
    monkeypatch.setattr(semantic, '_embedding', embed)
    assert 'calculus' in semantic.topic_scores('How do rates change?')
    assert CALCULUS['description'] in seen
    updated = dict(CALCULUS, description='Advanced calculus for integration and differentiation of functions.')
    assert client.put('/api/topics/calculus', json=updated).status_code == 200
    seen.clear()
    semantic.similarity('How do rates change?', ['calculus'], 'semantic')
    assert updated['description'] in seen
    assert CALCULUS['description'] not in seen


def test_topic_analysis_reads_configuration_in_current_transaction(client):
    import json
    add_calculus(client)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('UPDATE topics SET keywords=? WHERE id=?', (json.dumps(['antiderivative']), 'calculus'))
        assert analyze_text('Please explain the antiderivative.')['topic'] == 'calculus'
