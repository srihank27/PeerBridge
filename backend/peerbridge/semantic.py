"""Backend-only embedding model with an explicit, offline-safe keyword fallback."""

from functools import lru_cache
import os
from pathlib import Path
import threading

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_DIRECTORY_NAME = f"all-MiniLM-L6-v2-{MODEL_REVISION}"
ROOT = Path(__file__).resolve().parents[2]
TOPIC_DESCRIPTIONS = {
    "algebra": "introductory algebra equations with letters variables linear equations mathematical expressions",
    "geometry": "geometry triangles angles circles shapes area perimeter geometric proofs",
    "python": "Python computer programming code functions loops lists software debugging",
    "robotics": "robotics building robots motors sensors electronics robot engineering",
    "writing": "essay writing paragraphs grammar revision creative writing literature",
    "presentations": "public speaking presentations speech audience confidence giving a talk",
    "science": "science biology chemistry experiments scientific method cells plants lab",
    "physics": "physics mechanics forces motion velocity energy gravity electricity",
    "study_skills": "study skills time management homework organization revision planning exams notes",
    "school_transition": "new school making friends belonging welcome activities school transition peer guide",
}
_lock = threading.Lock()
_model = None
_attempted = False
_failure = None


def requested_mode():
    mode = os.environ.get("PEERBRIDGE_MATCHING", "auto").lower()
    return mode if mode in {"auto", "semantic", "keyword"} else "auto"


def get_model():
    global _model, _attempted, _failure
    if requested_mode() == "keyword":
        _failure = "Keyword mode was explicitly selected; no embedding model is running."
        return None
    with _lock:
        if _attempted:
            return _model
        _attempted = True
        cache = Path(os.environ.get("PEERBRIDGE_MODEL_CACHE", str(ROOT / ".cache" / "models")))
        model_dir = cache / MODEL_DIRECTORY_NAME
        # No network access here: downloads require the documented explicit setup command.
        # A plain snapshot directory also works on Windows accounts that cannot
        # create Hugging Face cache symlinks. Never load a partial download.
        if not (model_dir / "modules.json").is_file() or not (model_dir / "model.safetensors").is_file():
            _failure = "The embedding model is not cached. Keyword rules are running; run the explicit model download command to enable semantic matching."
            return None
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(str(model_dir), local_files_only=True, device="cpu")
        except Exception as exc:
            _failure = f"The cached embedding model could not be loaded ({type(exc).__name__}). Keyword rules are running."
        return _model


def status():
    model = get_model()
    return {"matching_mode": "semantic" if model is not None else "keyword", "model_name": MODEL_NAME if model is not None else None, "fallback_reason": None if model is not None else _failure}


def effective_mode(mode=None):
    if mode == "keyword":
        return "keyword"
    return status()["matching_mode"]


@lru_cache(maxsize=1024)
def _embedding(text):
    model = get_model()
    if model is None:
        return None
    return model.encode(text, normalize_embeddings=True, show_progress_bar=False)


def topic_scores(text, mode=None):
    if effective_mode(mode) != "semantic":
        return {}
    query = _embedding(text)
    return {topic: max(0.0, min(1.0, float(query @ _embedding(description)))) for topic, description in TOPIC_DESCRIPTIONS.items()}


def similarity(text, strengths, mode=None, topic=None):
    if not strengths:
        return 0.0
    if effective_mode(mode) != "semantic":
        return 1.0 if topic and topic in strengths else 0.0
    # Compare the actual request to declared competences. Embedding the chosen
    # canonical topic on both sides would make every identical topic score 1
    # and would erase semantic differences between individual requests.
    query = _embedding(text)
    return max(max(0.0, min(1.0, float(query @ _embedding(TOPIC_DESCRIPTIONS.get(s, s))))) for s in strengths)
