import os
import json
import re
from openai import OpenAI
from .json_utils import safe_json_load

# =====================
# INIT
# =====================
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set")

client = OpenAI(api_key=api_key)


# =====================
# MAIN AI FUNCTION
# =====================
def evaluate_ielts_writing(task1_text, task2_text, config):

    model = config["model"]

    prompt = f"""
You are a professional IELTS examiner (Band 9 level).

Your job is to give VERY DETAILED and HIGH-QUALITY evaluation.

⚠️ STRICT RULES:
- Return ONLY valid JSON
- No explanations outside JSON
- Be strict like real IELTS examiner
- Give LONG and useful feedback

JSON FORMAT:

{{
  "task1": {{
    "task": 0-9,
    "coherence": 0-9,
    "lexical": 0-9,
    "grammar": 0-9
  }},
  "task2": {{
    "task": 0-9,
    "coherence": 0-9,
    "lexical": 0-9,
    "grammar": 0-9
  }},

  "feedback": {{
    "task1": "Minimum 120 words detailed feedback",
    "task2": "Minimum 150 words detailed feedback",
    "improvements": [
      "Give at least 5 specific improvement points"
    ]
  }},

  "advanced": {{
    "common_mistakes": [
      "At least 6 VERY SPECIFIC mistakes from user's text"
    ],
    "better_vocabulary": [
      "At least 6 vocabulary upgrades with examples"
    ],
    "sample_rewrite": "Rewrite FULL Task 2 (introduction + 1 body paragraph at Band 8 level, minimum 120 words)"
  }}
}}

=== TASK 1 ===
{task1_text[:1200]}

=== TASK 2 ===
{task2_text[:1500]}
"""

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "Return ONLY JSON."},
            {"role": "user", "content": prompt},
        ],
        max_output_tokens=1500
    )

    content = response.output_text.strip()
    content = content.replace("```json", "").replace("```", "")

    print("🔥 AI RAW:", content)

    return content, response.usage


# =====================
# RETRY FUNCTION
# =====================
def evaluate_with_retry(task1, task2, config):
    for _ in range(2):
        try:
            content, usage = evaluate_ielts_writing(task1, task2, config)

            data = safe_json_load(content)

            if data:
                return data, usage

            print("❌ JSON FAILED:", content)

        except Exception as e:
            print("AI ERROR:", str(e))

    return None, None