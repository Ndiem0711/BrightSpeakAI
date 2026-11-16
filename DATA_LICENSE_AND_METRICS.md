# ML/DL source and evaluation notes

**Real supervised ML (optional):** `python ml/train_keyword_spotter.py --download` uses Google Speech Commands mini dataset, CC BY 4.0, and trains a RandomForest keyword recognizer with held-out speakers. Source: https://storage.googleapis.com/download.tensorflow.org/data/mini_speech_commands.zip and https://arxiv.org/abs/1804.03209 (P. Warden, 2018). Outputs `ml/models/keyword_spotter.joblib` and `ml/models/keyword_spotter_metrics.json` when executed. **Not run here.** It is a keyword-classification benchmark, not a pronunciation-quality score and not a child-speech benchmark.

**Real DL pretrained inference (optional):** `pip install -r requirements-ml.txt` installs faster-whisper, which downloads published pretrained Whisper weights on first use. No new neural model was trained in this build. Source: https://github.com/SYSTRAN/faster-whisper .

**What remains:** To develop validated child pronunciation scoring, obtain permissioned real child speech with teacher/phoneme ratings, train supervised model on teacher-scored speech, perform speaker-disjoint splits, report WER/CER, grade-wise error, score correlation, MAE, data quality and privacy analysis.
