# services/google_calendar.py
#
# All functions now take a `credentials` argument (a
# google.oauth2.credentials.Credentials object for the signed-in user,
# obtained from services.google_auth.get_current_credentials()).
#
# This replaces the old approach of one shared token.pickle / credentials.json
# on disk, which meant every user of the app was reading/writing the SAME
# Google account. Now each user authenticates with their own Google account
# (see services/google_auth.py) and events are created on *their* calendar.

from datetime import datetime, timedelta

from googleapiclient.discovery import build


def _get_service(credentials):
    if credentials is None:
        raise RuntimeError(
            "No Google credentials available. Please sign in with Google first."
        )
    return build("calendar", "v3", credentials=credentials)


def create_event(credentials, title, description, start_time: datetime, end_time: datetime):
    """
    Creates a single event on the signed-in user's primary Google Calendar.
    Returns a dict: {"id": ..., "htmlLink": ...}
    """

    service = _get_service(credentials)

    event_body = {
        "summary": title,
        "description": description or "",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
    }

    created_event = service.events().insert(
        calendarId="primary",
        body=event_body
    ).execute()

    return {
        "id": created_event.get("id"),
        "htmlLink": created_event.get("htmlLink"),
    }


def create_events_batch(credentials, schedule_items, base_date=None):
    """
    Creates a Google Calendar event for EVERY block in a generated schedule,
    on the signed-in user's own calendar.

    schedule_items: list of dicts with keys
        date (YYYY-MM-DD), time (HH:MM), end_time (HH:MM), title

    Returns a list of dicts: [{"title": ..., "id": ..., "htmlLink": ...}, ...]
    Any individual failures are captured per-item instead of stopping the batch.
    """

    results = []

    for item in schedule_items:
        try:
            date_str = item.get("date") or (
                base_date.strftime("%Y-%m-%d") if base_date else datetime.now().strftime("%Y-%m-%d")
            )

            start_dt = datetime.fromisoformat(f"{date_str}T{item['time']}:00")
            end_dt = datetime.fromisoformat(f"{date_str}T{item['end_time']}:00")

            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(
                    minutes=item.get("duration_minutes", 30)
                )

            event = create_event(credentials, item["title"], "", start_dt, end_dt)

            results.append({
                "title": item["title"],
                "id": event["id"],
                "htmlLink": event["htmlLink"],
                "status": "success",
            })

        except Exception as e:
            results.append({
                "title": item.get("title", "Unknown"),
                "id": None,
                "htmlLink": None,
                "status": f"failed: {e}",
            })

    return results


def update_google_event(credentials, event_id, title, description, start_time: datetime, end_time: datetime):
    service = _get_service(credentials)

    event_body = {
        "summary": title,
        "description": description or "",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
    }

    updated_event = service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event_body
    ).execute()

    return {
        "id": updated_event.get("id"),
        "htmlLink": updated_event.get("htmlLink"),
    }


def delete_google_event(credentials, event_id):
    service = _get_service(credentials)

    service.events().delete(
        calendarId="primary",
        eventId=event_id
    ).execute()

    return True


def sync_deleted_events(credentials=None):
    """
    Placeholder sync hook used by pages/calendar.py.
    Extend this to reconcile events deleted on Google's side with Supabase
    for the current user's credentials.
    """
    return None
