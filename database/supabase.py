import os
from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==========================
# GOOGLE OAUTH TOKEN STORAGE
# ==========================
#
# Lets a user close the app and come back later without re-doing the Google
# consent screen every time — we store their refresh token (and look it up
# by email) instead of keeping it only in memory/session.
#
# Run this SQL once in Supabase to create the table:
#
#   create table user_tokens (
#       id uuid primary key default gen_random_uuid(),
#       email text unique not null,
#       token_data jsonb not null,
#       updated_at timestamptz default now()
#   );

def save_user_token(email, token_data):
    payload = {
        "email": email,
        "token_data": token_data,
        "updated_at": datetime.now().isoformat(),
    }

    existing = (
        supabase.table("user_tokens")
        .select("id")
        .eq("email", email)
        .execute()
    )

    if existing.data:
        return (
            supabase.table("user_tokens")
            .update(payload)
            .eq("email", email)
            .execute()
        )

    return supabase.table("user_tokens").insert(payload).execute()


def get_user_token(email):
    if not email:
        return None

    result = (
        supabase.table("user_tokens")
        .select("token_data")
        .eq("email", email)
        .execute()
    )

    if result.data:
        return result.data[0]["token_data"]

    return None


def delete_user_token(email):
    return (
        supabase.table("user_tokens")
        .delete()
        .eq("email", email)
        .execute()
    )


# ==========================
# TASK OPERATIONS
# ==========================
#
# Tasks are now scoped per signed-in user via a `user_email` column, so one
# person's tasks/events never show up for another.
#
# Run this SQL once in Supabase (safe to run even if the table already has
# rows — new rows just need user_email going forward):
#
#   alter table tasks add column if not exists user_email text;

# Run this SQL once in Supabase (safe to run even if the table already has
# rows) so each task can store its AI-generated schedule blocks alongside it:
#
#   alter table tasks add column if not exists schedule jsonb;

def add_task(data, user_email=None):
    if user_email and "user_email" not in data:
        data = {**data, "user_email": user_email}
    return supabase.table("tasks").insert(data).execute()


def get_tasks(user_email=None):
    query = supabase.table("tasks").select("*")
    if user_email:
        query = query.eq("user_email", user_email)
    return query.execute()


def update_task(task_id, updates):
    return (
        supabase.table("tasks")
        .update(updates)
        .eq("id", task_id)
        .execute()
    )


def auto_update_task_status(user_email=None):

    result = get_tasks(user_email=user_email)

    if not result or not result.data:
        return

    now = datetime.now()

    for task in result.data:

        # Skip already completed tasks
        if task["status"] == "Completed":
            continue

        deadline = datetime.fromisoformat(task["deadline"])

        if deadline < now:

            update_task(
                task["id"],
                {
                    "status": "Completed"      # or "Overdue"
                }
            )


def delete_task(task_id):
    return (
        supabase.table("tasks")
        .delete()
        .eq("id", task_id)
        .execute()
    )


# ==========================
# HABIT OPERATIONS
# ==========================

def add_habit(data):
    return supabase.table("habits").insert(data).execute()


def get_habits():
    return supabase.table("habits").select("*").execute()


def update_habit(habit_id, updates):

    clean_updates = {}

    for key, value in updates.items():

        if hasattr(value, "item"):
            clean_updates[key] = value.item()
        else:
            clean_updates[key] = value

    return (
        supabase.table("habits")
        .update(clean_updates)
        .eq("id", habit_id)
        .execute()
    )


def delete_habit(habit_id):
    return (
        supabase.table("habits")
        .delete()
        .eq("id", habit_id)
        .execute()
    )