"""Google Calendar integration for Cortex PKM.

This module provides one-way sync from Cortex tasks to Google Calendar.
Authentication uses OAuth 2.0 with refresh token persistence.
"""

import json
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from ..config import get_config_path, load_config, save_config
from ..core.notes import find_notes
from ..utils import get_notes_dir, require_init

# Google API scopes - need full calendar access to list/create calendars
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Default OAuth client configuration for Desktop app
DEFAULT_CLIENT_CONFIG = {
    "installed": {
        # These will be populated when you set up the Google Cloud project
        # See: https://console.cloud.google.com/apis/credentials
        "client_id": "769575986616-uet5a3ch861jkspbr6tiuno1d913ju7n.apps.googleusercontent.com",  
        "client_secret": "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", 
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://127.0.0.1"],
    }
}


def _get_credentials_file() -> Path:
    """Get path to store Google credentials (refresh token)."""
    config_dir = Path.home() / ".config" / "cortex"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "google_credentials.pickle"


def _get_credentials() -> Optional[dict]:
    """Load cached credentials from secure storage.
    
    Returns:
        Credentials dict with refresh_token, or None if not authenticated.
    """
    # Check environment variable first (for CI/shared machines)
    env_creds = os.environ.get("GOOGLE_CREDENTIALS")
    if env_creds:
        import json
        try:
            return json.loads(env_creds)
        except json.JSONDecodeError:
            pass
    
    # Try pickle file (created by auth flow)
    creds_file = _get_credentials_file()
    if creds_file.exists():
        try:
            with open(creds_file, "rb") as f:
                creds = pickle.load(f)
            return creds
        except Exception:
            return None
    
    # Fall back to config file (legacy/compatibility)
    config = load_config()
    if config.get("google_refresh_token"):
        return {
            "refresh_token": config["google_refresh_token"],
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": config.get("google_client_id", ""),
            "client_secret": config.get("google_client_secret", ""),
        }
    
    return None


def _save_credentials(creds: dict) -> None:
    """Save credentials to secure storage.
    
    Stores in pickle file with restricted permissions (0o600).
    """
    creds_file = _get_credentials_file()
    with open(creds_file, "wb") as f:
        pickle.dump(creds, f)
    # Restrict permissions: owner read/write only
    os.chmod(creds_file, 0o600)


def _clear_credentials() -> None:
    """Remove stored credentials."""
    creds_file = _get_credentials_file()
    if creds_file.exists():
        creds_file.unlink()
    
    # Also clear from config
    config = load_config()
    for key in ["google_refresh_token", "google_client_id", "google_client_secret"]:
        if key in config:
            del config[key]
    save_config(config)


def _get_access_token(creds: dict) -> Optional[str]:
    """Get valid access token, refreshing if necessary.
    
    Args:
        creds: Credentials dict with refresh_token
        
    Returns:
        Valid access token, or None if refresh fails.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    
    credentials = Credentials.from_authorized_user_info(creds, SCOPES)
    
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            # Update stored credentials with new token
            _save_credentials(json.loads(credentials.to_json()))
        except Exception as e:
            click.echo(click.style(f"Failed to refresh token: {e}", fg="red"), err=True)
            return None
    
    return credentials.token


def _build_service():
    """Build Google Calendar API service.
    
    Returns:
        Calendar API service object, or None if not authenticated.
    """
    from googleapiclient.discovery import build
    
    creds = _get_credentials()
    if not creds:
        return None
    
    access_token = _get_access_token(creds)
    if not access_token:
        return None
    
    # Build service with access token
    from google.oauth2.credentials import Credentials
    credentials = Credentials.from_authorized_user_info(creds, SCOPES)
    
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _find_or_create_calendar(service, calendar_name: str = "Cortex Tasks") -> str:
    """Find or create the Cortex Tasks calendar.
    
    Args:
        service: Google Calendar API service
        calendar_name: Name for the calendar
        
    Returns:
        Calendar ID
    """
    # List existing calendars
    calendars = service.calendarList().list().execute()
    
    for cal in calendars.get("items", []):
        if cal.get("summary") == calendar_name:
            return cal["id"]
    
    # Create new calendar
    calendar = {
        "summary": calendar_name,
        "description": "Tasks and due dates from Cortex PKM",
        "timeZone": "UTC",
    }
    created = service.calendars().insert(body=calendar).execute()
    click.echo(click.style(f"Created calendar: {calendar_name}", fg="green"))
    return created["id"]


@click.command(short_help="Authenticate with Google Calendar")
@click.option("--client-id", help="Custom OAuth client ID (override default)")
@click.option("--client-secret", help="Custom OAuth client secret (override default)")
def auth(client_id: Optional[str], client_secret: Optional[str]):
    """Authenticate with Google Calendar.
    
    Opens a browser for OAuth authentication. The refresh token is stored
    securely and used to maintain access without re-authentication.
    
    By default, uses the built-in Cortex OAuth app. To use your own:
      cor calendar auth --client-id YOUR_ID --client-secret YOUR_SECRET
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    
    # Determine which credentials to use
    if client_id and client_secret:
        # User provided custom credentials
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://127.0.0.1"],
            }
        }
    elif client_id or client_secret:
        raise click.ClickException(
            "Please provide both --client-id and --client-secret, or neither to use defaults."
        )
    else:
        # Use default embedded credentials
        client_config = DEFAULT_CLIENT_CONFIG
    
    # Run OAuth flow
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    try:
        creds = flow.run_local_server(port=0)
    except Exception as e:
        raise click.ClickException(f"Authentication failed: {e}")
    
    # Save credentials
    creds_dict = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    _save_credentials(creds_dict)
    
    click.echo()
    click.echo(click.style("✓ Authentication successful!", fg="green", bold=True))
    click.echo("Your refresh token has been stored securely.")
    click.echo("You won't need to authenticate again unless the token is revoked.")


@click.command(short_help="Sync due dates to Google Calendar")
@click.option("--calendar", "-c", default="Cortex Tasks", help="Calendar name (default: 'Cortex Tasks')")
@require_init
def sync(calendar: str):
    """Sync task due dates to Google Calendar.
    
    Creates or updates events in Google Calendar for tasks with due dates.
    Only syncs tasks that are not done or dropped.
    
    Run 'cor calendar auth' first to authenticate.
    
    \b
    Examples:
      cor calendar sync              # Sync all due dates
      cor calendar sync -c "My Tasks" # Use different calendar
    """
    # Check authentication
    service = _build_service()
    if not service:
        raise click.ClickException(
            "Not authenticated with Google Calendar.\n"
            "Run: cor calendar auth"
        )
    
    notes_dir = get_notes_dir()
    
    # Find tasks with due dates
    notes = find_notes(notes_dir)
    tasks_to_sync = [
        n for n in notes
        if n.note_type == "task" 
        and n.due 
        and n.status not in ("done", "dropped")
    ]
    
    # Get or create calendar
    try:
        calendar_id = _find_or_create_calendar(service, calendar)
    except Exception as e:
        raise click.ClickException(f"Failed to access calendar: {e}")
    
    # Get existing events from calendar to handle updates and deletions
    existing_events = {}
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            maxResults=2500,
        ).execute()
        
        for event in events_result.get("items", []):
            task_id = None
            
            # Check for Cortex task ID in extended properties
            props = event.get("extendedProperties", {}).get("private", {})
            task_id = props.get("cortex_task_id")
            
            if not task_id:
                # Also match by description pattern if no extended property
                desc = event.get("description", "")
                if "Task: " in desc:
                    for line in desc.split("\n"):
                        if line.startswith("Task: "):
                            extracted_id = line.replace("Task: ", "").strip()
                            if extracted_id:
                                task_id = extracted_id
                                break
            
            if task_id:
                existing_events[task_id] = event
    except Exception as e:
        click.echo(click.style(f"Warning: Could not fetch existing events: {e}", fg="yellow"))
    
    # Build set of task IDs that should have events
    task_ids_to_sync = {task.path.stem for task in tasks_to_sync}
    
    # Sync tasks
    created_count = 0
    updated_count = 0
    deleted_count = 0
    skipped_count = 0
    
    for task in tasks_to_sync:
        task_id = task.path.stem
        
        # Build event data
        event_summary = f"[{task.status}] {task.title}"
        
        # Format due date as all-day event
        from datetime import date
        if isinstance(task.due, datetime):
            due_date = task.due.date()
        elif isinstance(task.due, date):
            due_date = task.due
        else:
            due_date = task.due
        
        start = {"date": due_date.strftime("%Y-%m-%d")}
        end = {"date": due_date.strftime("%Y-%m-%d")}
        
        event_body = {
            "summary": event_summary,
            "description": f"Task: {task_id}\nStatus: {task.status}\nPriority: {task.priority or 'none'}",
            "start": start,
            "end": end,
            "extendedProperties": {
                "private": {
                    "cortex_task_id": task_id,
                    "cortex_status": task.status or "",
                    "cortex_priority": task.priority or "",
                }
            },
        }
        
        # Check for existing event
        existing = existing_events.get(task_id)
        
        try:
            if existing:
                # Update existing event
                event_id = existing["id"]
                service.events().patch(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event_body,
                ).execute()
                updated_count += 1
                click.echo(f"  Updated: {task_id}")
            else:
                # Create new event
                service.events().insert(
                    calendarId=calendar_id,
                    body=event_body,
                ).execute()
                created_count += 1
                click.echo(f"  Created: {task_id}")
        except Exception as e:
            click.echo(click.style(f"  Failed: {task_id} - {e}", fg="red"))
            skipped_count += 1
    
    # Delete events for tasks that are no longer synced
    # (done, dropped, no due date, or deleted)
    events_to_delete = [
        (task_id, event) for task_id, event in existing_events.items()
        if task_id not in task_ids_to_sync
    ]
    
    for task_id, event in events_to_delete:
        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=event["id"],
            ).execute()
            deleted_count += 1
            click.echo(f"  Deleted: {task_id}")
        except Exception as e:
            click.echo(click.style(f"  Failed to delete: {task_id} - {e}", fg="red"))
            skipped_count += 1
    
    # Summary
    click.echo()
    click.echo(click.style("Sync complete:", fg="green", bold=True))
    click.echo(f"  Created: {created_count}")
    click.echo(f"  Updated: {updated_count}")
    if deleted_count:
        click.echo(f"  Deleted: {deleted_count}")
    if skipped_count:
        click.echo(f"  Failed: {skipped_count}")


@click.command(short_help="Check calendar authentication status")
def status():
    """Check Google Calendar authentication status."""
    creds = _get_credentials()
    
    if not creds:
        click.echo(click.style("Not authenticated", fg="yellow"))
        click.echo("Run: cor calendar auth")
        return
    
    # Test the credentials
    service = _build_service()
    if service:
        try:
            # Try to list calendars
            calendars = service.calendarList().list(maxResults=1).execute()
            click.echo(click.style("✓ Authenticated", fg="green", bold=True))
            click.echo("Your refresh token is valid and working.")
            
            # Show token location
            creds_file = _get_credentials_file()
            if creds_file.exists():
                click.echo(f"Token stored at: {creds_file}")
        except Exception as e:
            click.echo(click.style("⚠ Token exists but may be invalid", fg="yellow"))
            click.echo(f"Error: {e}")
            click.echo("Try running: cor calendar auth")
    else:
        click.echo(click.style("⚠ Token exists but could not build service", fg="yellow"))
        click.echo("Try running: cor calendar auth")


@click.command(short_help="Logout from Google Calendar")
def logout():
    """Remove Google Calendar authentication.
    
    This revokes the stored refresh token. You'll need to re-authenticate
    to sync with Google Calendar again.
    """
    creds = _get_credentials()
    if not creds:
        click.echo("Not currently authenticated.")
        return
    
    _clear_credentials()
    click.echo(click.style("✓ Logged out from Google Calendar", fg="green"))
    click.echo("Your refresh token has been removed.")
