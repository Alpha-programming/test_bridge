from openai import OpenAI
import json

client = OpenAI()

def evaluate_speaking(transcript):
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": "You are a strict IELTS examiner."},
            {
                "role": "user",
                "content": f"""
Evaluate IELTS speaking.

Transcript:
{transcript}

Return JSON:
{{
  "fluency": 0-9,
  "grammar": 0-9,
  "vocabulary": 0-9,
  "overall": 0-9,
  "feedback": "text"
}}
"""
            }
        ]
    )

    return json.loads(response.choices[0].message.content)