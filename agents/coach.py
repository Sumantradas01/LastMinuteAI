# agents/coach.py

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


def productivity_coach(tasks):

    prompt = f"""
You are a world-class productivity coach.

Analyze these tasks:

{tasks}

Provide:

1. Top priorities
2. Time management advice
3. Productivity suggestions
4. Potential risks
5. Recommended action for today

Keep response concise and actionable.
"""

    response = model.generate_content(prompt)

    return response.text