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
    _post("/me/events", payload)
    return f"Meeting '{subject}' created for {start_dt} Dubai time."


def _get_email_body(message_id: str) -> str:
    import re
    data = _get(f"/me/messages/{message_id}", **{"$select": "subject,from,body,receivedDateTime"})
    subject = data.get("subject", "(no subject)")
    sender  = data.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
    body    = data.get("body", {}).get("content", "")
    body    = re.sub(r"<[^>]+>", " ", body)
    body    = re.sub(r"\s+", " ", body).strip()
    return f"From: {sender}\nSubject: {subject}\n\n{body[:1200]}"


def _reply_email(message_id: str, body: str) -> str:
    _post(f"/me/messages/{message_id}/reply",
          {"message": {"body": {"contentType": "Text", "content": body}}})
    return "Reply sent."


def _flag_email(message_id: str, flagged: bool = True) -> str:
    status = "flagged" if flagged else "notFlagged"
    token = _get_access_token()
    r = httpx.patch(f"{_GRAPH}/me/messages/{message_id}",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"flag": {"flagStatus": status}}, timeout=15)
    r.raise_for_status()
    return f"Email {'flagged' if flagged else 'unflagged'}."


def _delete_email(message_id: str) -> str:
    token = _get_access_token()
    r = httpx.delete(f"{_GRAPH}/me/messages/{message_id}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=15)
    r.raise_for_status()
    return "Email moved to trash."


def _list_contacts(query: str = "", limit: int = 5) -> str:
    params: dict = {"$top": limit, "$select": "displayName,emailAddresses,mobilePhone"}
    if query:
        params["$search"] = f'"{query}"'
    data = _get("/me/contacts", **params)
    contacts = data.get("value", [])
    if not contacts:
        return "No contacts found."
    lines = [f"Found {len(contacts)} contact(s):"]
    for c in contacts:
        email = c.get("emailAddresses", [{}])[0].get("address", "")
        phone = c.get("mobilePhone", "") or ""
        lines.append(f"  {c['displayName']} — {email} {phone}".strip())
    return "\n".join(lines)


def _update_event(event_id: str, subject: str = None, start_dt: str = None,
                  end_dt: str = None, body: str = None) -> str:
    payload: dict = {}
    if subject:
        payload["subject"] = subject
    if start_dt:
        payload["start"] = {"dateTime": start_dt, "timeZone": "Asia/Dubai"}
    if end_dt:
        payload["end"] = {"dateTime": end_dt, "timeZone": "Asia/Dubai"}
    if body:
        payload["body"] = {"contentType": "Text", "content": body}
    token = _get_access_token()
    r = httpx.patch(f"{_GRAPH}/me/events/{event_id}",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=payload, timeout=15)
    r.raise_for_status()
    return "Event updated."


def _cancel_event(event_id: str) -> str:
    token = _get_access_token()
    r = httpx.post(f"{_GRAPH}/me/events/{event_id}/cancel",
                   headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                   json={"comment": "Cancelled via JARVIS."}, timeout=15)
    r.raise_for_status()
    return "Event cancelled."


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
                    days: int = 7, start_dt: str = None, end_dt: str = None,
                    message_id: str = None, event_id: str = None,
                    flagged: bool = True) -> str:
    try:
        match action:
            case "unread":            return _unread_count()
            case "recent_emails":     return _recent_emails(limit)
            case "search_emails":     return _search_emails(query or "", limit)
            case "send_email":        return _send_email(to or "", subject or "", body or "")
            case "get_email_body":    return _get_email_body(message_id or "")
            case "reply_email":       return _reply_email(message_id or "", body or "")
            case "flag_email":        return _flag_email(message_id or "", flagged)
            case "delete_email":      return _delete_email(message_id or "")
            case "list_contacts":     return _list_contacts(query or "", limit)
            case "todays_meetings":   return _todays_meetings()
            case "upcoming_meetings": return _upcoming_meetings(days)
            case "update_event":      return _update_event(event_id or "", subject, start_dt, end_dt, body)
            case "cancel_event":      return _cancel_event(event_id or "")
            case "create_event":
                if not start_dt:
                    return "[Error] start_dt is required to create an event."
                if not end_dt:
                    from datetime import datetime, timedelta
                    end_dt = (datetime.fromisoformat(start_dt) + timedelta(hours=1)).isoformat()
                return _create_event(subject or "Meeting", start_dt, end_dt, body or "")
            case _:
                return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] outlook_manager({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "outlook_manager",
    "description": (
        "Access Microsoft Outlook email and calendar via Microsoft Graph. "
        "Email: unread, recent_emails, search_emails, send_email, get_email_body, reply_email, flag_email, delete_email, list_contacts. "
        "Calendar: todays_meetings, upcoming_meetings, create_event, update_event, cancel_event."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "unread", "recent_emails", "search_emails", "send_email",
                    "get_email_body", "reply_email", "flag_email", "delete_email", "list_contacts",
                    "todays_meetings", "upcoming_meetings", "create_event", "update_event", "cancel_event",
                ],
                "description": "Action to perform.",
            },
            "query":      {"type": "string",  "description": "Search keyword — for search_emails or list_contacts."},
            "limit":      {"type": "integer", "description": "Max results (default 5)."},
            "to":         {"type": "string",  "description": "Recipient address — for send_email."},
            "subject":    {"type": "string",  "description": "Subject — for send_email, create_event, update_event."},
            "body":       {"type": "string",  "description": "Body text — for send_email, reply_email, create_event, update_event."},
            "message_id": {"type": "string",  "description": "Message ID — for get_email_body, reply_email, flag_email, delete_email."},
            "event_id":   {"type": "string",  "description": "Event ID — for update_event, cancel_event."},
            "flagged":    {"type": "boolean", "description": "True to flag, False to unflag (flag_email)."},
            "days":       {"type": "integer", "description": "Days ahead for upcoming_meetings (default 7)."},
            "start_dt":   {"type": "string",  "description": "Event start YYYY-MM-DDTHH:MM:SS Dubai time."},
            "end_dt":     {"type": "string",  "description": "Event end YYYY-MM-DDTHH:MM:SS Dubai time."},
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "outlook_manager": lambda **kw: outlook_manager(**kw),
}
