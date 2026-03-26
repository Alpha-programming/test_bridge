from openai import OpenAI
import json

client = OpenAI()

def evaluate_speaking(transcript):
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "system",
                "content": "You are a strict IELTS speaking examiner."
            },
            {
                "role": "user",
                "content": f"""
Evaluate this IELTS Speaking answer.

Transcript:
{transcript}

Return ONLY JSON:

{{
  "fluency": number (0-9),
  "lexical": number (0-9),
  "grammar": number (0-9),
  "overall": number (0-9),
  "feedback": {{
    "fluency": "...",
    "lexical": "...",
    "grammar": "...",
    "improvements": ["...", "..."]
  }}
}}
"""
            }
        ]
    )

    return json.loads(response.choices[0].message.content)

def evaluate_full_speaking(text):
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "system",
                "content": "You are an IELTS speaking examiner."
            },
            {
                "role": "user",
                "content": f"""
Evaluate full IELTS speaking test:

{text}

Return JSON:
{{
 "fluency": 0-9,
 "lexical": 0-9,
 "grammar": 0-9,
 "pronunciation": 0-9,
 "overall": 0-9,
 "feedback": {{
    "summary": "...",
    "improvements": []
 }}
}}
"""
            }
        ]
    )

    return json.loads(response.choices[0].message.content)