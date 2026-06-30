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


def generate_plan(
    title,
    description,
    deadline
):

    prompt = f"""
You are an AI scheduling assistant.

Create ONLY a schedule.

DO NOT explain.
DO NOT give tips.
DO NOT write paragraphs.
DO NOT write introductions.
DO NOT write conclusions.

Return ONLY this format.

Task: {title}

Description: {description}

Deadline: {deadline}

Output Format:

📅 Schedule

09:00 - 10:00 : Task 1

10:00 - 10:15 : Break

10:15 - 11:30 : Task 2

11:30 - 12:00 : Review

12:00 - Finish

Return ONLY the schedule.
"""

    response = model.generate_content(prompt)

    return response.text