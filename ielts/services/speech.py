from openai import OpenAI

client = OpenAI()

import subprocess
import os

def convert_to_wav(input_path):
    output_path = input_path.rsplit(".", 1)[0] + ".wav"

    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        output_path
    ]

    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return output_path

def transcribe_audio(file_path):
    wav_path = convert_to_wav(file_path)

    with open(wav_path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=f,
            model="gpt-4o-transcribe"
        )

    return result.text