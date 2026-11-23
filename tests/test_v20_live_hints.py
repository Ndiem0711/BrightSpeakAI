"""Face-to-face hint content must stay limited to the approved question."""
from pathlib import Path
from app.live import _hint_instruction, _prompt_instruction, _prompt
ROOT=Path(__file__).resolve().parents[1]
EXERCISE={'id':'GS3-001-001','topic':'Animals','grade':3,'question':'What is your favourite animal?','sample_answer':'I like cats.'}

def test_live_prompt_speaks_full_question_and_uses_sample_as_hint():
    prompt=_prompt(3,EXERCISE,False)
    assert 'SPEAK THE ENTIRE QUESTION' in prompt
    assert EXERCISE['question'] in prompt
    assert EXERCISE['sample_answer'] in prompt
    assert EXERCISE['question'] in _prompt_instruction(EXERCISE)
    assert 'You can say: '+EXERCISE['sample_answer'] in _hint_instruction(EXERCISE,False)
    assert 'You can try saying: '+EXERCISE['sample_answer'] in _hint_instruction(EXERCISE,True)

def test_backend_exposes_only_an_approved_hint_for_active_prompt():
    backend=(ROOT/'app/live.py').read_text(encoding='utf-8')
    assert "msg.get('type') == 'request_hint'" in backend
    assert "asked_id != str(active_exercise['id'])" in backend
    assert "'type':'hint_ready'" in backend
    assert 'if hint_sent:' in backend
    assert 'SPEAK' in _hint_instruction(EXERCISE,False)

def test_ui_hides_model_answer_until_hint_and_timers_reset():
    html=(ROOT/'app/static/index.html').read_text(encoding='utf-8')
    ui=(ROOT/'app/static/features.js').read_text(encoding='utf-8')
    assert '/static/live-hints.js' in html
    assert 'liveSampleQuestion' in ui and 'liveSampleAnswer' in ui
    assert 'answer.parentElement.hidden=true' in ui
    assert 'liveHints.assistantFinished()' in ui
    assert 'liveHints.speechDetected()' in ui
    assert 'clearLiveHintTimers();liveHintTurn=false' in ui
