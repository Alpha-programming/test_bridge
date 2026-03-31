import json
from collections import Counter

def build_user_reading_profile(user_tests):
    total_tests = len(user_tests)

    if total_tests == 0:
        return {}

    total_accuracy = 0
    total_scores = []
    all_mistakes = Counter()

    for t in user_tests:
        total_accuracy += t.accuracy or 0

        if t.score is not None:
            total_scores.append(t.score)

        if t.mistake_stats:
            try:
                data = json.loads(t.mistake_stats)

                # 🔥 ensure dict
                if isinstance(data, dict):
                    all_mistakes.update(data)

            except Exception as e:
                print("Mistake parse error:", e)

    avg_accuracy = round(total_accuracy / total_tests, 1)

    avg_score = (
        round(sum(total_scores) / len(total_scores), 1)
        if total_scores else 0
    )

    return {
        "total_tests": total_tests,
        "avg_accuracy": avg_accuracy,
        "avg_score": avg_score,

        # 🔥 limit top 5 only (cleaner AI)
        "weak_types": dict(all_mistakes.most_common(5))
    }