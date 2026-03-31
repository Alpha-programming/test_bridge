from openai import OpenAI
import json

client = OpenAI()

def analyze_listening(profile):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an IELTS listening coach. Return ONLY JSON."
            },
            {
                "role": "user",
                "content": f"""
Analyze IELTS Listening profile:

{json.dumps(profile, indent=2)}

Return JSON:
{{
 "level": "",
 "strengths": [],
 "weaknesses": [],
 "strategy": [],
 "focus_plan": [],
 "motivation": ""
}}
"""
            }
        ]
    )

    content = response.choices[0].message.content.strip()
    content = content.replace("```json", "").replace("```", "")

    try:
        return json.loads(content)
    except:
        return {}