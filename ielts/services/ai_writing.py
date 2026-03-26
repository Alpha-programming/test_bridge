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
def evaluate_ielts_writing(task1_text, task2_text, model="gpt-5-mini"):

    prompt = f"""
Evaluate IELTS Writing Task 1 and Task 2.

Return ONLY valid JSON (no text before or after).

{{
  "task1": {{"task": 0-9, "coherence": 0-9, "lexical": 0-9, "grammar": 0-9, "band": 0-9}},
  "task2": {{"task": 0-9, "coherence": 0-9, "lexical": 0-9, "grammar": 0-9, "band": 0-9}},
  "final_band": 0-9,
  "feedback": {{
    "task1": "detailed feedback",
    "task2": "detailed feedback",
    "improvements": ["point1", "point2", "point3"]
  }}
}}

Task 1:
{task1_text[:900]}

Task 2:
{task2_text[:1100]}
"""

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "You are a strict IELTS examiner. Return only JSON."},
            {"role": "user", "content": prompt},
        ],
        max_output_tokens=800,
        reasoning={"effort": "low"}  # 🔥 THIS FIXES YOUR MAIN ISSUE
    )

    content = response.output_text

    print("AI RAW:", content)

    return content, response.usage


# =====================
# RETRY FUNCTION
# =====================
def evaluate_with_retry(task1, task2, model):
    for _ in range(2):
        try:
            content, usage = evaluate_ielts_writing(task1, task2, model)

            data = safe_json_load(content)

            if data:
                return data, usage

        except Exception as e:
            print("AI ERROR:", str(e))

    return None, None