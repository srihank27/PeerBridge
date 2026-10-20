"""Explicitly download the pinned public model; inference never downloads files."""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.peerbridge.semantic import MODEL_NAME, MODEL_REVISION


def main():
    cache = Path(os.environ.get('PEERBRIDGE_MODEL_CACHE', str(ROOT / '.cache' / 'models'))).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    model_directory = cache / f'all-MiniLM-L6-v2-{MODEL_REVISION}'
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    print(f'Downloading {MODEL_NAME} at revision {MODEL_REVISION} into {model_directory}', flush=True)
    snapshot_download(
        repo_id=MODEL_NAME,
        revision=MODEL_REVISION,
        # A plain local snapshot works on Windows without symlink privileges.
        local_dir=str(model_directory),
        allow_patterns=[
            'modules.json', 'config.json', 'config_sentence_transformers.json',
            'sentence_bert_config.json', 'model.safetensors', 'tokenizer.json',
            'tokenizer_config.json', 'special_tokens_map.json', 'vocab.txt',
            '1_Pooling/config.json', 'README.md',
        ],
    )
    model = SentenceTransformer(str(model_directory), local_files_only=True, device='cpu')
    vector = model.encode('PeerBridge model verification', normalize_embeddings=True)
    print(f'Verified local model: {len(vector)} embedding dimensions. Restart the backend to enable semantic matching.', flush=True)


if __name__ == '__main__':
    main()
