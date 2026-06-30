# agents/replanner.py

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)


def replan_task(task):

    prompt = f"""
The user missed progress on the following task:

{task}

Create a revised plan.

Include:

1. Updated timeline
2. Faster execution strategy
3. Daily milestones
4. Risk mitigation
5. Final recommendation

Return in markdown.
"""

    response = model.generate_content(prompt)

    return response.text