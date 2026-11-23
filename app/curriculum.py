from __future__ import annotations
from functools import lru_cache
from json import loads
from pathlib import Path
from typing import Any
from .config import ROOT_DIR
from .db import db

CURRICULUM_FILE = ROOT_DIR / 'data' / 'global_success_original_speaking.json'

@lru_cache(maxsize=1)
def curated_prompts() -> tuple[dict[str, Any], ...]:
    doc = loads(CURRICULUM_FILE.read_text(encoding='utf-8'))
    prompts = doc['prompts']
    if any(int(p['grade']) not in range(1, 6) for p in prompts):
        raise ValueError('Invalid practice grade')
    return tuple(prompts)

def prompts_for_student(student: dict[str, Any]) -> list[dict[str, Any]]:
    grade = int(student.get('grade') or 3)
    curated = [dict(p, source='curriculum') for p in curated_prompts() if p['grade'] == grade]
    assigned = db.fetchall('''
        SELECT l.id,l.grade,l.topic,l.target_text,l.hint
        FROM lessons l JOIN teacher_lesson_assignments a ON a.lesson_id=l.id
        WHERE a.student_id=? AND l.grade=? AND l.active=1 AND l.owner_teacher_id IS NOT NULL
        ORDER BY l.created_at DESC
    ''', (student['id'], grade))
    teacher = [dict(id='TEACHER:'+l['id'], grade=grade, unit_title='GV giao bài', topic=l['topic'],
                    question='Please say: '+l['target_text'], sample_answer=l['target_text'],
                    skill='listen-repeat', source='teacher', source_kind='teacher_authored') for l in assigned]
    return teacher+curated

def resolve_student_prompt(student: dict[str, Any], prompt_id: str) -> dict[str, Any] | None:
    current = next((p for p in prompts_for_student(student) if p['id']==prompt_id), None)
    if current:
        return current
    return legacy_review_prompts(student).get(prompt_id)


def teacher_access_to_student(teacher_id: str, student_id: str, grade: int) -> bool:
    row = db.fetchone('''SELECT 1 AS yes FROM users u JOIN teacher_students ts ON ts.student_id=u.id
                         WHERE u.id=? AND u.role='student' AND u.active=1 AND u.grade=? AND ts.teacher_id=?''',
                      (student_id,grade,teacher_id))
    return bool(row)

GRADE_MAX_WORDS = {1:8, 2:12, 3:18, 4:24, 5:30}

@lru_cache(maxsize=1)
def legacy_catalog():
    return loads((ROOT_DIR / 'data' / 'legacy_v15.json').read_text(encoding='utf-8'))

def legacy_review_prompts(student):
    pending = {r['prompt_id'] for r in db.fetchall(
        'SELECT prompt_id FROM speaking_reviews WHERE user_id=? AND pending=1', (student['id'],))}
    return {p['id']:p for p in legacy_catalog()['prompts']
            if p['id'] in pending and p['grade']==student.get('grade')}

@lru_cache(maxsize=1)
def source_books():
    return loads((ROOT_DIR / 'data' / 'source_books.json').read_text(encoding='utf-8'))

@lru_cache(maxsize=1)
def unit_contexts():
    units = loads(CURRICULUM_FILE.read_text(encoding='utf-8'))['units']
    return {(u['grade'], u['topic']):
            'Model exchanges: ' + '; '.join(u['models']) +
            '. Relevant words: ' + ', '.join(u['vocabulary']) + '.'
            for u in units}

def unit_context(grade, topic):
    return unit_contexts().get((grade, topic), '')
