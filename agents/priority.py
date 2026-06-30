import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)


def predict_priority(
    title,
    description,
    deadline
):

    prompt = f"""
You are a task prioritization AI.

Task:
{title}

Description:
{description}

Deadline:
{deadline}

Classify the task urgency into exactly one of these labels:

HIGH
MEDIUM
LOW

Rules:
- Return ONLY the single word label (HIGH, MEDIUM, or LOW).
- No punctuation, no explanation, no extra text.
"""

    response = model.generate_content(prompt)
    raw = response.text.strip().upper()

    # Robustly extract the priority label even if the model adds extra text
    match = re.search(r"\b(HIGH|MEDIUM|LOW)\b", raw)
    if match:
        return match.group(1)

    # Safe fallback
    return "MEDIUM"