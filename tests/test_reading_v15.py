import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app import speaking_review as reading
from app.db import db
from test_v13_learning import auth, wav


def test_pupil_reads_retries_and_clears(monkeypatch):
    with TestClient(app) as c:
        headers=auth(c)
        prompts=c.get('/api/v1/live/prompts',headers=headers).json()['prompts']
        prompt=next(p for p in prompts if p['source']=='curriculum' and len(p['sample_answer'].split())>=3)
        target=prompt['sample_answer']
        transcript=target.split(' ',1)[1]
        monkeypatch.setattr(reading,'transcribe_audio',lambda _: (transcript,'test'))
        def submit(pid):
            return c.post('/api/v1/speaking/read',headers=headers,data={'prompt_id':pid},files={'audio':('a.wav',wav(),'audio/wav')})
        for _ in range(2):
            d=submit(prompt['id']).json()
            assert d['pending'] and d['words'] and d['topic']==prompt['topic']
        def queue():return c.get('/api/v1/speaking/review',headers=headers).json()
        assert len([r for r in queue() if r['prompt_id']==prompt['id']])==1
        assert reading.review_list({'id':'another-pupil','grade':3})==[]
        assert submit('unknown').status_code==404
        assert c.get('/api/v1/speaking/review',headers=auth(c,'teacher@demo.com','teacher123')).status_code==403
        transcript=''
        assert submit(prompt['id']).status_code==422
        assert any(r['prompt_id']==prompt['id'] for r in queue())
        transcript=target
        assert not submit(prompt['id']).json()['pending']
        assert not any(r['prompt_id']==prompt['id'] for r in queue())


def test_all_curriculum_samples_have_audio():
    root=Path(__file__).resolve().parents[1]
    aliases=json.loads((root/'app/static/audio-index.js').read_text().split(' = ',1)[1].strip().rstrip(';'))
    for p in json.loads((root/'data/global_success_original_speaking.json').read_text())['prompts']:
        key=aliases.get(p['id'],p['id'])
        clip=root/'app/static/readings'/key[2]/(key+'.mp3')
        assert clip.read_bytes().startswith(b'ID3') and clip.stat().st_size>1000

def test_sgk_source_pages_and_playback_routes():
    from app.curriculum import curated_prompts, source_books, unit_context
    from collections import defaultdict
    books={b['name']:b['pages'] for b in source_books()}
    assert len(books)==8
    covered=defaultdict(set)
    map_only=set()
    for row in curated_prompts():
        total=books[row['book']]
        assert 1<=row['book_map_pdf']<=total
        for field in ('source_pdf','lesson_pdf','practice_pdf'):
            if row.get(field):
                assert 1<=row[field]<=total
        if row.get('unit'):
            key=row['grade'],row['unit']
            if not row['lesson_pdf']:
                map_only.add(key)
            if row.get('lesson_no'):
                covered[key].add(row['lesson_no'])
    assert len(covered)==61 and len(map_only)==31
    assert all(parts=={1,2,3} for parts in covered.values())
    assert 'goldfish' in unit_context(3,'Unit 16 · My pets')
    assert not unit_context(4,'Unit 16 · My pets')
    with TestClient(app) as c:
        headers=auth(c)
        assert len(c.get('/api/v1/curriculum/books',headers=headers).json())==2
        active={l['id'] for l in c.get('/api/v1/lessons',headers=headers).json()}
        assert {p['id'] for p in curated_prompts() if p['grade']==3}<=active
