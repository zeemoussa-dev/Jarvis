"""
Microsoft Outlook agent — email and calendar via Microsoft Graph API.
Uses a stored refresh token to get access tokens automatically.
"""

import httpx
from datetime import datetime, timezone, timedelta, date
import config

_TENANT       = "consumers"
_TOKEN_URL    = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/token"
_GRAPH        = "https://graph.microsoft.com/v1.0"
_access_token: str | None = None
_TZ_HEADER    = {"Prefer": 'outlook.timezone="Asia/Dubai"'}  # UTC+4


def _get_access_token() -> str:
    global _access_token
    data = {
        "client_id":     config.MS_CLIENT_ID,
        "grant_type":    "refresh_token",
        "refresh_token": config.MS_REFRESH_TOKEN,
        "scope":         "Mail.Read Mail.Send Calendars.Read Calendars.ReadWrite User.Read offline_access",
    }
    r = httpx.post(_TOKEN_URL, data=data, timeout=15)
    r.raise_for_status()
    _access_token = r.json()["access_token"]
    return _access_token


def _headers() -> dict:
    token = _get_access_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get(path: str, extra_headers: dict = None, **params) -> dict:
    headers = {**_headers(), **(extra_headers or {})}
    r = httpx.get(f"{_GRAPH}{path}", headers=headers, params=params or None, timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path: str, payload: dict) -> dict:
    r = httpx.post(f"{_GRAPH}{path}", headers=_headers(), json=payload, timeout=15)
    r.raise_for_status()
    return r.json() if r.content else {}


# ── Actions ───────────────────────────────────────────────────────────────────

def _unread_count() -> str:
    data = _get("/me/mailFolders/Inbox", **{"$select": "unreadItemCount,totalItemCount"})
    unread = data.get("unreadItemCount", 0)
    total  = data.get("totalItemCount", 0)
    return f"You have {unread} unread email{'s' if unread != 1 else ''} out of {total} in your inbox."


def _recent_emails(limit: int = 5) -> str:
    data = _get(
        "/me/messages",
        **{
            "$top": limit,
            "$orderby": "receivedDateTime desc",
            "$select": "subject,from,receivedDateTime,isRead,bodyPreview",
            "$filter": "isDraft eq false",
        }
    )
    emails = data.get("value", [])
    if not emails:
        return "Your inbox is empty."
    lines = [f"Your {len(emails)} most recent emails:"]
    for e in emails:
        sender = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subject = e.get("subject", "(no subject)")
        dt = e.get("receivedDateTime", "")[:10]
        read = "" if e.get("isRead") else " [UNREAD]"
        lines.append(f"  {dt} — {sender}: {subject}{read}")
    return "\n".join(lines)


def _search_emails(query: str, limit: int = 5) -> str:
    data = _get(
        "/me/messages",
        **{
            "$top": limit,
            "$search": f'"{query}"',
            "$select": "subject,from,receivedDateTime,bodyPreview",
        }
    )
    emails = data.get("value", [])
    if not emails:
        return f"No emails found matching '{query}'."
    lines = [f"Search results for '{query}':"]
    for e in emails:
        sender = e.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        subject = e.get("subject", "(no subject)")
        dt = e.get("receivedDateTime", "")[:10]
        lines.append(f"  {dt} — {sender}: {subject}")
    return "\n".join(lines)


def _send_email(to: str, subject: str, body: str) -> str:
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        }
    }
    _post("/me/sendMail", payload)
    return f"Email sent to {to} with subject '{subject}'."


def _create_event(subject: str, start_dt: str, end_dt: str, body: str = "") -> str:
    payload = {
        "subject": subject,
        "body": {"contentType": "Text", "content": body},
        "start": {"dateTime": start_dt, "timeZone": "Asia/Dubai"},
        "end":   {"dateTime": end_dt,   "timeZone": "Asia/Dubai"},
    }
    ev = _post("/me/events", payload)
    return f"Meeting '{subject}' created for {start_dt} Dubai time."


def _all_calendar_events(start: datetime, end: datetime) -> list[dict]:
    """Fetch events from all calendars and merge."""
    cals = _get("/me/calendars", **{"$select": "id,name"})
    all_events = []
    for cal in cals.get("value", []):
        try:
            data = _get(
                f"/me/calendars/{cal['id']}/calendarView",
                extra_headers=_TZ_HEADER,
                **{
                    "startDateTime": start.isoformat(),
                    "endDateTime":   end.isoformat(),
                    "$select":       "subject,start,end,location,organizer",
                    "$top":          20,
                }
            )
            for ev in data.get("value", []):
                ev["_calName"] = cal["name"]
                all_events.append(ev)
        except Exception:
            pass
    all_events.sort(key=lambda e: e.get("start", {}).get("dateTime", ""))
    return all_events


def _todays_meetings() -> str:
    dubai_offset = timezone(timedelta(hours=4))
    now_local    = datetime.now(dubai_offset)
    start        = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end          = start + timedelta(days=1)

    events = _all_calendar_events(start, end)
    if not events:
        return "You have no meetings scheduled for today."
    lines = [f"You have {len(events)} meeting{'s' if len(events) != 1 else ''} today:"]
    for ev in events:
        subject  = ev.get("subject", "Untitled")
        start_dt = ev.get("start", {}).get("dateTime", "")[:16].replace("T", " ")
        end_dt   = ev.get("end",   {}).get("dateTime", "")[11:16]
        loc      = ev.get("location", {}).get("displayName", "")
        loc_str  = f" at {loc}" if loc else ""
        lines.append(f"  {start_dt} – {end_dt}{loc_str}: {subject}")
    return "\n".join(lines)


def _upcoming_meetings(days: int = 7) -> str:
    dubai_offset = timezone(timedelta(hours=4))
    now_local    = datetime.now(dubai_offset)
    end          = now_local + timedelta(days=days)

    events = _all_calendar_events(now_local, end)
    if not events:
        return f"No meetings in the next {days} days."
    lines = [f"{len(events)} upcoming meeting{'s' if len(events) != 1 else ''} in the next {days} days:"]
    for ev in events:
        subject  = ev.get("subject", "Untitled")
        start_dt = ev.get("start", {}).get("dateTime", "")[:16].replace("T", " ")
        cal_name = ev.get("_calName", "")
        lines.append(f"  {start_dt}: {subject} ({cal_name})")
    return "\n".join(lines)


# ── Single tool ───────────────────────────────────────────────────────────────

def outlook_manager(action: str, query: str = None, limit: int = 5,
                    to: str = None, subject: str = None, body: str = None,
                    days: int = 7, start_dt: str = None, end_dt: str = None) -> str:
    try:
        if action == "unread":
            return _unread_count()
        elif action == "recent_emails":
            return _recent_emails(limit)
        elif action == "search_emails":
            return _search_emails(query or "", limit)
        elif action == "send_email":
            return _send_email(to or "", subject or "", body or "")
        elif action == "todays_meetings":
            return _todays_meetings()
        elif action == "upcoming_meetings":
            return _upcoming_meetings(days)
        elif action == "create_event":
            if not start_dt:
                return "[Error] start_dt is required to create an event."
            if not end_dt:
                # Default to 1 hour duration if no end time given
                from datetime import datetime, timedelta
                end_dt = (datetime.fromisoformat(start_dt) + timedelta(hours=1)).isoformat()
            return _create_event(subject or "Meeting", start_dt, end_dt, body or "")
        else:
            return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] outlook_manager({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "outlook_manager",
    "description": (
        "Access Microsoft Outlook email and calendar via Microsoft Graph. "
        "Use 'unread' for unread email count. "
        "Use 'recent_emails' to list the latest emails. "
        "Use 'search_emails' to find emails by keyword or sender. "
        "Use 'send_email' to compose and send an email. "
        "Use 'todays_meetings' to see today's calendar. "
        "Use 'upcoming_meetings' to see meetings in the next N days. "
        "Use 'create_event' to add a new calendar event — requires subject, start_dt and end_dt in format YYYY-MM-DDTHH:MM:SS."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["unread", "recent_emails", "search_emails", "send_email", "todays_meetings", "upcoming_meetings"],
                "description": "Action to perform.",
            },
            "query":   {"type": "string",  "description": "Search keyword — for search_emails."},
            "limit":   {"type": "integer", "description": "Max results (default 5)."},
            "to":      {"type": "string",  "description": "Recipient email address — for send_email."},
            "subject": {"type": "string",  "description": "Email subject — for send_email."},
            "body":    {"type": "string",  "description": "Email body text — for send_email."},
            "days":     {"type": "integer", "description": "Days ahead for upcoming_meetings (default 7)."},
            "start_dt": {"type": "string",  "description": "Event start in YYYY-MM-DDTHH:MM:SS — for create_event."},
            "end_dt":   {"type": "string",  "description": "Event end in YYYY-MM-DDTHH:MM:SS — for create_event."},
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "outlook_manager": lambda **kw: outlook_manager(**kw),
}
