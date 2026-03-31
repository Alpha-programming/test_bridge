from openai import OpenAI
import json

client = OpenAI()

def evaluate_full_speaking(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an IELTS speaking examiner. Return ONLY valid JSON."
            },
            {
                "role": "user",
                "content": f"""
Evaluate IELTS Speaking test.

{text}

Return ONLY JSON:

{{
 "fluency": 0-9,
 "lexical": 0-9,
 "grammar": 0-9,
 "pronunciation": 0-9,

 "feedback": {{
    "fluency": "short feedback",
    "lexical": "short feedback",
    "grammar": "short feedback",
    "pronunciation": "short feedback",
    "summary": "overall summary",
    "improvements": ["point1","point2","point3"]
 }}
}}
"""
            }
        ],
        max_tokens=700
    )

    content = response.choices[0].message.content.strip()

    # 🔥 CLEAN JSON
    content = content.replace("```json", "").replace("```", "")

    print("🔥 SPEAKING RAW:", content)

    return json.loads(content)