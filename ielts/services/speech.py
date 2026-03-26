from openai import OpenAI

client = OpenAI()

def transcribe_audio(file_path):
    with open(file_path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=f,
            model="gpt-4o-transcribe"
        )
    return result.text