from openai import OpenAI
import json

client = OpenAI()


def analyze_overall(profile):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional IELTS reading coach. "
                    "Be accurate, practical, and helpful. "
                    "Return ONLY valid JSON. No explanation outside JSON."
                )
            },
            {
                "role": "user",
                "content": f"""
Analyze this IELTS Reading student profile:

{json.dumps(profile, indent=2)}

Return ONLY JSON:

{{
 "level": "Band estimate (e.g. Band 6.5)",
 "strengths": ["2-3 points"],
 "weaknesses": ["2-4 points"],
 "strategy": ["specific improvement steps"],
 "focus_plan": ["daily/weekly plan"],
 "motivation": "short motivating message"
}}
"""
            }
        ],
        max_tokens=700
    )

    content = response.choices[0].message.content.strip()

    # 🔥 CLEAN RESPONSE
    content = content.replace("```json", "").replace("```", "").strip()

    print("🔥 OVERALL AI RAW:", content)

    # 🔥 SAFE JSON PARSE
    try:
        return json.loads(content)

    except Exception as e:
        print("❌ JSON FAILED:", e)

        # fallback structure
        return {
            "level": "Unknown",
            "strengths": [],
            "weaknesses": ["AI response parsing failed"],
            "strategy": ["Try again later"],
            "focus_plan": [],
            "motivation": "Keep practicing!"
        }