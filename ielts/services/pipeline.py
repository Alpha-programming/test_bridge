from .speech import transcribe_audio
from .evaluation import evaluate_speaking


def process_speaking(attempt):
    file_path = attempt.audio.path

    # 1. Transcription
    transcript = transcribe_audio(file_path)

    # 2. GPT evaluation
    data = evaluate_speaking(transcript)

    # (temporary pronunciation score)
    pronunciation_score = 6.5

    # Save
    attempt.transcript = transcript
    attempt.fluency_score = data["fluency"]
    attempt.grammar_score = data["grammar"]
    attempt.vocabulary_score = data["vocabulary"]
    attempt.overall_band = data["overall"]
    attempt.pronunciation_score = pronunciation_score
    attempt.feedback = data["feedback"]
    attempt.save()

    return {
        "transcript": transcript,
        **data,
        "pronunciation": pronunciation_score
    }