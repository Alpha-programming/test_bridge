import json
from collections import Counter

def build_user_listening_profile(user_tests):

    total_tests = len(user_tests)

    if total_tests == 0:
        return {}

    total_accuracy = 0
    scores = []
    mistakes = Counter()

    for t in user_tests:
        total_accuracy += t.accuracy or 0

        if t.score is not None:
            scores.append(t.score)

        if t.mistake_stats:
            try:
                data = json.loads(t.mistake_stats)
                if isinstance(data, dict):
                    mistakes.update(data)
            except:
                pass

    return {
        "total_tests": total_tests,
        "avg_accuracy": round(total_accuracy / total_tests, 1),
        "avg_score": round(sum(scores)/len(scores),1) if scores else 0,
        "weak_types": dict(mistakes.most_common(5))
    }