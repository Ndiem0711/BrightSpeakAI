from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def test_old_v6_no_longer_overwrites_new_live():
    code=(ROOT/'app/static/features.js').read_text(encoding='utf-8')
    assert 'renderLive=renderLiveV6' not in code
    assert 'renderLiveV6()' not in code
    assert 'function renderLive()' in code
    assert 'id="liveBibi"' in code


def test_live_audio_worklet_and_mirror():
    code=(ROOT/'app/static/features.js').read_text(encoding='utf-8')
    work=(ROOT/'app/static/live-audio-worklet.js').read_text(encoding='utf-8')
    assert "live-audio-worklet.js" in code
    assert "scaleX(-1)" in code
    assert "stopLiveCamera()" in code
    assert 'bufferedAmount' in code
    assert 'brightspeak-voice-worklet' in work


def test_v9_lesson_manifest_and_status():
    manifest=(ROOT/'data/lesson_manifest.csv').read_text(encoding='utf-8-sig')
    assert len(manifest.splitlines())==126
    status=json.loads((ROOT/'ml/DATASET_STATUS.json').read_text(encoding='utf-8'))
    assert status['audio_samples_bundled']==0
    assert status['lesson_text_count']==125
    assert status['trained_model_bundled'] is True
    assert (ROOT/'ml/models/keyword_spotter.joblib').exists()
