"""Explainable V13 recommendations; only eligible lessons and real attempts are used."""
from .scoring import _words


def recommend_lessons(lessons, attempts, limit=5):
    real = [a for a in attempts if a.get('ai_mode') != 'demo']
    by_lesson = {}
    for attempt in real:  # newest first
        by_lesson.setdefault(attempt['lesson_id'], []).append(attempt)
    recent = real[:5]
    average = sum(float(a['overall']) for a in recent) / len(recent) if recent else None
    # These are product rules, not empirically validated proficiency thresholds.
    band = 'support' if average is None or average < 60 else ('practice' if average < 85 else 'extend')
    output = []
    for lesson in lessons:
        history = by_lesson.get(lesson['id'], [])
        latest = history[0] if history else None
        word_count = len(_words(lesson['target_text']))
        if latest and float(latest['overall']) < 70:
            priority = 0
            reason = 'Ôn lại bài có kết quả gần nhất còn thấp.'
        elif not latest:
            priority = 1
            reason = 'Bài mới phù hợp khối lớp của em.'
        else:
            priority = 2
            reason = 'Củng cố bài đã luyện.'
        complexity = word_count if band == 'support' else (-word_count if band == 'extend' else abs(word_count - 7))
        output.append((priority, complexity, lesson['id'], {**lesson, 'reason': reason,
            'last_score': float(latest['overall']) if latest else None, 'level_rule': band}))
    return [item[3] for item in sorted(output, key=lambda x: x[:3])[:limit]]
