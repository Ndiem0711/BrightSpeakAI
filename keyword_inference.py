"""Optional ML inference (only after locally trained artifact exists)."""
from pathlib import Path

MODEL_PATH=Path(__file__).resolve().parent/'models'/'keyword_spotter.joblib'
_cached=None

def predict_keyword(wav_bytes):
    global _cached
    if not MODEL_PATH.exists():return None
    from io import BytesIO
    import tempfile
    import joblib
    from .train_keyword_spotter import load_features
    if _cached is None:_cached=joblib.load(MODEL_PATH)
    with tempfile.NamedTemporaryFile(suffix='.wav') as f:
        f.write(wav_bytes);f.flush()
        features=load_features(f.name)
    model=_cached['model'];prob=model.predict_proba([features])[0]
    idx=int(prob.argmax())
    return {'keyword':str(model.classes_[idx]),'probability':round(float(prob[idx]),3),
            'model_type':'RandomForest keyword spotter','warning':'Không phải điểm phát âm'}
