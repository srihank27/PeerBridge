"""Optional offline integration tests using the actual downloaded embedding model."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.peerbridge import semantic
from backend.peerbridge.main import app


MODEL_CACHE = Path(os.environ.get('PEERBRIDGE_MODEL_CACHE', str(semantic.ROOT / '.cache' / 'models')))
pytestmark = pytest.mark.skipif(
    not (MODEL_CACHE / semantic.MODEL_DIRECTORY_NAME / 'model.safetensors').is_file(),
    reason='Run scripts/download_model.py first; these tests never download a model.',
)


@pytest.fixture
def semantic_client(tmp_path, monkeypatch):
    monkeypatch.setenv('PEERBRIDGE_DB', str(tmp_path / 'semantic.sqlite3'))
    monkeypatch.setenv('PEERBRIDGE_MATCHING', 'semantic')
    with TestClient(app) as client:
        yield client


def test_real_cached_embeddings_recommend_and_accept(semantic_client):
    client = semantic_client
    health = client.get('/api/health').json()
    assert health['matching_mode'] == 'semantic', health
    response = client.post('/api/missions', json={
        'requester_id': 'learner-aria',
        'text': 'I cannot solve equations with letters, and I am embarrassed to ask in class.',
    })
    assert response.status_code == 201, response.text
    mission = response.json()
    assert mission['topic'] == 'algebra'
    result = client.post(f"/api/missions/{mission['id']}/recommendations").json()
    assert result['matching_mode'] == 'semantic'
    assert result['candidates'], result
    assert result['resources']
    candidate = result['candidates'][0]
    # Actual request embeddings must be compared with competence descriptions;
    # substituting the same topic vector would incorrectly produce S == 1.
    assert 0 < candidate['component_scores']['S'] < 0.99
    accepted = client.post('/api/matches', json={
        'mission_id': mission['id'], 'mentor_id': candidate['mentor']['id'],
    })
    assert accepted.status_code == 201, accepted.text
    assert all(p['remaining_capacity'] >= 0 for p in client.get('/api/profiles').json())


def test_semantic_engine_cannot_override_private_routing(semantic_client):
    client = semantic_client
    response = client.post('/api/missions', json={
        'requester_id': 'learner-aria',
        'text': 'I need algebra help but someone is bullying me and I do not feel safe.',
    })
    assert response.status_code == 201
    mission = response.json()
    assert mission['route'] == 'private_support'
    recommendation = client.post(f"/api/missions/{mission['id']}/recommendations").json()
    assert recommendation['candidates'] == []
    assert mission['id'] not in {m['id'] for m in client.get('/api/missions').json()}
