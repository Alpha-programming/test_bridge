from .speech import transcribe_audio
from .evaluation import evaluate_speaking
import json

def combine_scores(data, pronunciation_score):
    fluency = data["fluency"]
    lexical = data["lexical"]
    grammar = data["grammar"]

    overall = round(
        (fluency + lexical + grammar + pronunciation_score) / 4, 1
    )

    return overall


def process_speaking(attempt):
    file_path = attempt.audio.path

    # 1. TRANSCRIPT
    transcript = transcribe_audio(file_path)

    # 2. GPT
    data = evaluate_speaking(transcript)

    # 3. PRONUNCIATION (temporary logic)
    pronunciation_score = 6.5

    # 4. FINAL BAND
    overall = combine_scores(data, pronunciation_score)

    # SAVE
    attempt.transcript = transcript
    attempt.fluency_score = data["fluency"]
    attempt.vocabulary_score = data["lexical"]
    attempt.grammar_score = data["grammar"]
    attempt.pronunciation_score = pronunciation_score
    attempt.overall_band = overall
    attempt.feedback = json.dumps(data["feedback"])
    attempt.save()

    return {
        "band": overall,
        "feedback": data["feedback"]
    }