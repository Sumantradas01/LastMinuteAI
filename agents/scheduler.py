# agents/scheduler.py

import json
import logging
import re
from datetime import datetime, timedelta

from agents.gemini_client import model

logger = logging.getLogger(__name__)


def _extract_json_array(text: str) -> str:
    """
    Pulls a JSON array out of a raw model response, tolerating:
    - ```json ... ``` or ``` ... ``` code fences
    - leading/trailing prose around the array
    - stray text before/after the [ ... ] block
    """
    text = text.strip()

    # Strip markdown code fences if present, anywhere in the string
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # If there's still leading/trailing junk, isolate the outermost [ ... ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return text.strip()


def generate_schedule(title, description, deadline):
    """
    Generates a realistic, time-anchored schedule for a task.

    Returns a list of dicts:
    [
        {
            "date": "2026-06-30",
            "time": "09:00",
            "end_time": "10:00",
            "title": "Research and outline",
            "duration_minutes": 60
        },
        ...
    ]
    """

    now = datetime.now()

    # Normalize deadline: st.date_input returns a date object; assume 23:59 EOD.
    # If it's already a datetime, use it as-is.
    if isinstance(deadline, datetime):
        deadline_dt = deadline
    else:
        deadline_dt = datetime.combine(
            deadline,
            datetime.max.time().replace(hour=23, minute=59, second=0, microsecond=0),
        )

    hours_remaining = max((deadline_dt - now).total_seconds() / 3600, 1)

    # Work blocks should start at least 15 minutes from now, rounded up to
    # the next half-hour so the schedule never shows a past start time.
    minutes_until_start = 15
    start_candidate = now + timedelta(minutes=minutes_until_start)
    round_to = 30
    remainder = start_candidate.minute % round_to
    if remainder:
        start_candidate += timedelta(minutes=(round_to - remainder))
    start_candidate = start_candidate.replace(second=0, microsecond=0)

    # Estimate how many JSON items we might need, to size max_output_tokens
    # generously enough that Gemini doesn't get truncated mid-array for
    # short-but-detailed descriptions (e.g. "assignments and projects").
    est_blocks = max(2, min(20, int(hours_remaining // 1) + 4))
    max_tokens = min(2000, 300 + est_blocks * 80)

    prompt = f"""
You are an AI scheduling assistant. Build a REALISTIC, TIME-ACCURATE schedule
for completing the task below before its deadline.

Current date/time: {now.strftime("%Y-%m-%d %H:%M")} ({now.strftime("%A")})
Earliest available start: {start_candidate.strftime("%Y-%m-%d %H:%M")} — do NOT schedule anything before this time.
Deadline: {deadline_dt.strftime("%Y-%m-%d %H:%M")} ({deadline_dt.strftime("%A")})
Hours remaining until deadline: {round(hours_remaining, 1)}

Task: {title}
Description: {description}

Rules:
- Read the description carefully. If it mentions multiple distinct items
  (e.g. "assignments and projects", "report and presentation"), create a
  SEPARATE block for each item — do not merge them into one generic block.
- If the description mentions a specific time budget (e.g. "in two hours"),
  the SUM of all work block durations must match that budget as closely as
  possible (breaks do not count toward the work budget).
- The FIRST block must start at or after the "Earliest available start" time above. Never schedule in the past.
- If hours_remaining is small (< 6), compress the plan into focused blocks today, ending before the deadline.
- If hours_remaining is large, spread work across multiple days leading up to the deadline,
  with realistic daily sessions (e.g. 1-3 hours/day), not one giant block.
- Include short breaks (10-15 min) between long focus blocks (> 60 min).
- Each block must have a clear, SPECIFIC title describing exactly what work it covers
  (not "Task 1", not "Work on: {title}").
- All times must be in 24-hour "HH:MM" format.
- The final block's end_time must be on or before the deadline.
- Return ONLY a valid JSON array. No markdown, no code fences, no explanations, no headings.

Each item must contain exactly these keys:
- "date" (YYYY-MM-DD)
- "time" (HH:MM start time)
- "end_time" (HH:MM end time)
- "title" (specific description of the work block)
- "duration_minutes" (integer)

Example:

[
  {{
    "date": "{now.strftime("%Y-%m-%d")}",
    "time": "09:00",
    "end_time": "10:00",
    "title": "Research and outline key sections",
    "duration_minutes": 60
  }},
  {{
    "date": "{now.strftime("%Y-%m-%d")}",
    "time": "10:00",
    "end_time": "10:10",
    "title": "Short break",
    "duration_minutes": 10
  }}
]
"""

    raw_text = ""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "top_p": 0.9,
                "top_k": 30,
                "max_output_tokens": max_tokens,
            },
        )

        raw_text = (response.text or "").strip()
        cleaned = _extract_json_array(raw_text)

        schedule = json.loads(cleaned)

        if not isinstance(schedule, list) or not schedule:
            raise ValueError("Parsed JSON was not a non-empty list")

        clean_schedule = []
        for item in schedule:
            clean_schedule.append({
                "date": item.get("date", now.strftime("%Y-%m-%d")),
                "time": item.get("time", "09:00"),
                "end_time": item.get("end_time", item.get("time", "09:00")),
                "title": item.get("title", "Work session"),
                "duration_minutes": int(item.get("duration_minutes", 60)),
            })

        clean_schedule.sort(key=lambda x: f"{x['date']} {x['time']}")

        return clean_schedule

    except Exception as e:
        # Log the raw model output so you can see exactly why parsing failed
        # (truncation, stray prose, malformed JSON, etc.) instead of
        # silently dropping into the generic single-block fallback.
        logger.warning(
            "generate_schedule: failed to parse Gemini response (%s). Raw text was:\n%s",
            e,
            raw_text,
        )

        fallback_end = start_candidate + timedelta(hours=1)

        return [
            {
                "date": start_candidate.strftime("%Y-%m-%d"),
                "time": start_candidate.strftime("%H:%M"),
                "end_time": fallback_end.strftime("%H:%M"),
                "title": f"Work on: {title or 'Unable to generate schedule'}",
                "duration_minutes": 60,
            }
        ]