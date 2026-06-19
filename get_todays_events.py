#!/usr/bin/env python3
"""
Holt die heutigen Termine aus Google Calendar und formatiert sie
als Text-Liste, die per Signal (CallMeBot) verschickt werden kann.
"""

import os
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_credentials():
    """Lädt die Service-Account-Credentials aus der Umgebungsvariable."""
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_info = json.loads(creds_json)
    return service_account.Credentials.from_service_account_info(
        creds_info, scopes=SCOPES
    )


def get_todays_events(service, calendar_id):
    """Holt alle Termine für den heutigen Tag (UTC-Tagesfenster)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + datetime.timedelta(days=1)

    time_min = start_of_day.isoformat()
    time_max = end_of_day.isoformat()

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return events_result.get("items", [])


def format_event_time(event):
    """Formatiert die Startzeit eines Events als HH:MM oder 'Ganztägig'."""
    start = event["start"].get("dateTime", event["start"].get("date"))
    if "T" in start:
        dt = datetime.datetime.fromisoformat(start)
        return dt.strftime("%H:%M")
    else:
        return "Ganztägig"


def format_message(events):
    """Baut den Nachrichtentext zusammen: Begrüßung + Zeitstempel + Termine."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.datetime.now().strftime("%d.%m.%Y")

    lines = [f"Hallo Giuliano! Nachricht um {now_str}", ""]
    lines.append(f"📅 Termine heute ({today_str}):")

    if not events:
        lines.append("Keine Termine heute. 🎉")
    else:
        for event in events:
            time_str = format_event_time(event)
            title = event.get("summary", "(Ohne Titel)")
            lines.append(f"- {time_str} {title}")

    return "\n".join(lines)


def main():
    calendar_id = os.environ["GOOGLE_CALENDAR_ID"]

    credentials = get_credentials()
    service = build("calendar", "v3", credentials=credentials)

    events = get_todays_events(service, calendar_id)
    message = format_message(events)

    print(message)

    # Für GitHub Actions: Nachricht in Output-Datei schreiben,
    # damit der nächste Step sie verwenden kann
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write("message<<EOF\n")
            f.write(message)
            f.write("\nEOF\n")


if __name__ == "__main__":
    main()
