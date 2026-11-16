from __future__ import annotations

import io
import math
import re
import wave
from array import array
from difflib import SequenceMatcher
from typing import Any


def normalize_text(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> list[str]:
    return [w for w in normalize_text(text).split(" ") if w]


def acoustic_features(wav_bytes: bytes) -> dict[str, float]:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            nframes = wf.getnframes()
            if sample_width != 2:
                raise ValueError("Only 16-bit PCM WAV is supported")
            raw = wf.readframes(nframes)
    except Exception as exc:
        raise ValueError("Audio must be a valid 16-bit PCM WAV recording") from exc

    samples = array("h")
    samples.frombytes(raw)
    if channels > 1:
        samples = array("h", samples[::channels])
    if not samples or frame_rate <= 0:
        raise ValueError("Audio recording is empty")

    duration = len(samples) / float(frame_rate)
    if duration < 0.25:
        raise ValueError("Recording is too short")

    abs_samples = [abs(v) for v in samples]
    rms = math.sqrt(sum(float(v) * float(v) for v in samples) / len(samples)) / 32768.0

    # 20 ms windows estimate pauses/silence without external DSP dependencies.
    win = max(1, int(frame_rate * 0.02))
    window_rms: list[float] = []
    for start in range(0, len(samples), win):
        chunk = samples[start:start + win]
        if not chunk:
            continue
        value = math.sqrt(sum(float(v) * float(v) for v in chunk) / len(chunk)) / 32768.0
        window_rms.append(value)
    peak = max(window_rms) if window_rms else 0.0
    silence_threshold = max(0.006, peak * 0.12)
    silence_ratio = (
        sum(1 for x in window_rms if x < silence_threshold) / len(window_rms)
        if window_rms else 1.0
    )
    mean_w = sum(window_rms) / len(window_rms) if window_rms else 0.0
    variance = sum((x - mean_w) ** 2 for x in window_rms) / len(window_rms) if window_rms else 0.0
    energy_variation = math.sqrt(variance)
    return {
        "duration": round(duration, 3),
        "rms": round(rms, 5),
        "silence_ratio": round(silence_ratio, 4),
        "energy_variation": round(energy_variation, 5),
    }


def score_pronunciation(target: str, transcript: str, features: dict[str, float]) -> dict[str, Any]:
    target_n = normalize_text(target)
    transcript_n = normalize_text(transcript)
    target_words = _words(target)
    said_words = _words(transcript)

    alignment = align_words(target_words, said_words)
    matched = sum(row['status'] == 'matched' for row in alignment)
    errors = sum(row['status'] != 'matched' for row in alignment)
    accuracy = max(0.0, 100.0 * (1.0 - errors / max(1, len(target_words))))
    completeness = 100.0 * matched / max(1, len(target_words))

    duration = max(features["duration"], 0.1)
    wpm = (max(1, len(said_words)) / duration) * 60.0
    # Primary learners commonly benefit from a moderate speaking pace.
    fluency = max(25.0, 100.0 - abs(wpm - 105.0) * 0.55 - features["silence_ratio"] * 22.0)

    # Prosody is a transparent acoustic proxy based on pause balance and energy variation,
    # not an emotion/confidence score and not phoneme-level diagnosis.
    variation_component = min(1.0, features["energy_variation"] / 0.035) * 35.0
    pause_component = max(0.0, 65.0 - features["silence_ratio"] * 55.0)
    prosody = max(30.0, min(100.0, variation_component + pause_component))

    accuracy = max(0.0, min(100.0, accuracy))
    completeness = max(0.0, min(100.0, completeness))
    fluency = max(0.0, min(100.0, fluency))
    overall = 0.45 * accuracy + 0.20 * fluency + 0.20 * completeness + 0.15 * prosody

    weakest = min(
        {"accuracy": accuracy, "fluency": fluency, "completeness": completeness, "prosody": prosody},
        key=lambda k: {"accuracy": accuracy, "fluency": fluency, "completeness": completeness, "prosody": prosody}[k],
    )
    advice = {
        "accuracy": "Listen to the model sentence and repeat it in short chunks.",
        "fluency": "Try shadowing: listen, then repeat the whole phrase without stopping after each word.",
        "completeness": "Read once slowly and make sure every word is included.",
        "prosody": "Use sentence stress and small natural pauses instead of speaking with one flat rhythm.",
    }[weakest]

    return {
        "word_alignment": alignment,
        "assessment_method": "word-edit-distance-and-acoustic-proxies-v13",
        "phoneme_assessment": False,
        "accuracy": round(accuracy, 1),
        "fluency": round(fluency, 1),
        "completeness": round(completeness, 1),
        "prosody": round(prosody, 1),
        "overall": round(overall, 1),
        "wpm": round(wpm, 1),
        "weakest": weakest,
        "feedback": advice,
    }


def align_words(reference, spoken):
    """Levenshtein alignment of ASR words, NOT acoustic/phoneme forced alignment."""
    n, m = len(reference), len(spoken)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): cost[i][0] = i
    for j in range(m + 1): cost[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i][j] = min(cost[i-1][j] + 1, cost[i][j-1] + 1,
                cost[i-1][j-1] + (reference[i-1] != spoken[j-1]))
    rows = []
    i, j = n, m
    while i or j:
        if i and j and cost[i][j] == cost[i-1][j-1] + (reference[i-1] != spoken[j-1]):
            rows.append({'expected': reference[i-1], 'heard': spoken[j-1],
                'status': 'matched' if reference[i-1] == spoken[j-1] else 'substitution'})
            i -= 1; j -= 1
        elif i and cost[i][j] == cost[i-1][j] + 1:
            rows.append({'expected': reference[i-1], 'heard': '', 'status': 'omission'})
            i -= 1
        else:
            rows.append({'expected': '', 'heard': spoken[j-1], 'status': 'insertion'})
            j -= 1
    return list(reversed(rows))


def validate_speech_signal(features):
    if features['rms'] < 0.003 or features['silence_ratio'] > 0.98:
        raise ValueError('Bản ghi quá nhỏ hoặc gần như im lặng. Em hãy nói gần mic rồi ghi lại.')
    if features['duration'] > 45:
        raise ValueError('Mỗi bản ghi tối đa 45 giây. Em hãy nói một câu ngắn rồi dừng.')
