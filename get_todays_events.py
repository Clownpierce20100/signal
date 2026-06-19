#!/usr/bin/env python3
"""
Holt die heutigen Termine aus Google Calendar + das Wetter und
formatiert beides als Text-Nachricht, die per Signal (CallMeBot)
verschickt werden kann.
"""

import os
import json
import datetime
import urllib.request
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Koordinaten für die Wetterabfrage (Nürnberg).
# Falls du umziehst oder einen anderen Ort willst, hier anpassen.
LATITUDE = 49.4521
LONGITUDE = 11.0767
LOCATION_NAME = "Nürnberg"

# WMO Weather Codes -> kurze deutsche Beschreibung + Emoji
# Quelle: Open-Meteo Doku (WMO Code Tabelle)
WEATHER_CODES = {
    0: ("Klarer Himmel", "☀️"),
    1: ("Überwiegend klar", "🌤️"),
    2: ("Teilweise bewölkt", "⛅"),
    3: ("Bedeckt", "☁️"),
    45: ("Nebel", "🌫️"),
    48: ("Reifnebel", "🌫️"),
    51: ("Leichter Nieselregen", "🌦️"),
    53: ("Nieselregen", "🌦️"),
    55: ("Starker Nieselregen", "🌦️"),
    61: ("Leichter Regen", "🌧️"),
    63: ("Regen", "🌧️"),
    65: ("Starker Regen", "🌧️"),
    66: ("Gefrierender Regen", "🌨️"),
    67: ("Starker gefrierender Regen", "🌨️"),
    71: ("Leichter Schneefall", "🌨️"),
    73: ("Schneefall", "🌨️"),
    75: ("Starker Schneefall", "❄️"),
    77: ("Schneegriesel", "❄️"),
    80: ("Leichte Regenschauer", "🌦️"),
    81: ("Regenschauer", "🌦️"),
    82: ("Heftige Regenschauer", "⛈️"),
    85: ("Leichte Schneeschauer", "🌨️"),
    86: ("Starke Schneeschauer", "🌨️"),
    95: ("Gewitter", "⛈️"),
    96: ("Gewitter mit Hagel", "⛈️"),
    99: ("Starkes Gewitter mit Hagel", "⛈️"),
}


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


def get_weather():
    """Holt das aktuelle Wetter + Tageswerte von Open-Meteo (kostenlos, kein API-Key nötig)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&current=temperature_2m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        "&timezone=Europe%2FBerlin"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())

        current_temp = data["current"]["temperature_2m"]
        current_code = data["current"]["weather_code"]
        temp_max = data["daily"]["temperature_2m_max"][0]
        temp_min = data["daily"]["temperature_2m_min"][0]

        desc, emoji = WEATHER_CODES.get(current_code, ("Unbekannt", "🌡️"))

        return {
            "current_temp": current_temp,
            "temp_max": temp_max,
            "temp_min": temp_min,
            "description": desc,
            "emoji": emoji,
        }
    except Exception as e:
        print(f"Wetter konnte nicht geladen werden: {e}")
        return None


def format_event_time(event):
    """Formatiert die Startzeit eines Events als HH:MM oder 'Ganztägig'."""
    start = event["start"].get("dateTime", event["start"].get("date"))
    if "T" in start:
        dt = datetime.datetime.fromisoformat(start)
        return dt.strftime("%H:%M")
    else:
        return "Ganztägig"


def format_message(events, weather):
    """Baut den Nachrichtentext zusammen: Begrüßung + Wetter + Termine."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.datetime.now().strftime("%d.%m.%Y")

    lines = [f"Hallo! Nachricht um {now_str}", ""]

    # Wetter-Block
    if weather:
        lines.append(f"{weather['emoji']} Wetter {LOCATION_NAME}: {weather['description']}")
        lines.append(
            f"Aktuell {weather['current_temp']:.0f}°C "
            f"(Tag: {weather['temp_min']:.0f}°C bis {weather['temp_max']:.0f}°C)"
        )
        lines.append("")

    # Termine-Block
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
    weather = get_weather()
    message = format_message(events, weather)

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
