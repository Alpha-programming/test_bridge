import json
import re


def safe_json_load(content):
    try:
        return json.loads(content)
    except:
        # remove ```json blocks if exist
        content = re.sub(r"```json|```", "", content).strip()

        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            return json.loads(content[start:end])
        except:
            return None