"""Remote inbox via Telegram bot for Cortex CLI."""

import json
from datetime import datetime
from pathlib import Path
from urllib import request, error

import click
import frontmatter

from ..schema import DATE_TIME

def pull_remote_inbox(notes_dir: Path, bot_token: str) -> int:
    """Fetch Telegram messages, append to backlog, delete them.

    Args:
        notes_dir: Path to vault root
        bot_token: Telegram bot API token

    Returns:
        Number of messages added to backlog

    Raises:
        click.ClickException: If API calls fail
    """
    base_url = f"https://api.telegram.org/bot{bot_token}"

    # 1. Fetch messages from Telegram
    try:
        with request.urlopen(f"{base_url}/getUpdates") as response:
            data = json.loads(response.read())
    except error.URLError as e:
        raise click.ClickException(f"Failed to fetch Telegram messages: {e}")
    except json.JSONDecodeError:
        raise click.ClickException("Invalid response from Telegram API")

    if not data.get("ok"):
        error_msg = data.get("description", "Unknown error")
        raise click.ClickException(f"Telegram API error: {error_msg}")

    updates = data.get("result", [])

    # Debug: show what we got
    click.echo(f"Debug: Received {len(updates)} updates from Telegram", err=True)

    if not updates:
        return 0

    # 2. Extract message texts
    messages = []
    update_ids = []
    for update in updates:
        update_id = update.get("update_id")
        message = update.get("message", {})
        text = message.get("text", "").strip()

        # Debug: show what we're seeing
        click.echo(f"Debug: Update {update_id}, message: {message}, text: '{text}'", err=True)

        if text and update_id is not None:
            messages.append(text)
            update_ids.append(update_id)

    click.echo(f"Debug: Extracted {len(messages)} messages", err=True)

    if not messages:
        return 0

    # 3. Append to backlog
    backlog_path = notes_dir / "backlog.md"
    if not backlog_path.exists():
        raise click.ClickException("No backlog.md found. Run 'cor init' first.")

    post = frontmatter.load(backlog_path)
    lines = (post.content or "").splitlines()

    # Ensure Inbox section exists
    inbox_idx = next((i for i, line in enumerate(lines) if line.strip() == "## Inbox"), None)
    if inbox_idx is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("## Inbox")
        inbox_idx = len(lines) - 1

    # Find insertion point (end of inbox section, before next heading)
    insert_idx = inbox_idx + 1
    for j in range(inbox_idx + 1, len(lines)):
        if lines[j].startswith("## "):
            insert_idx = j
            break
        insert_idx = j + 1

    # Insert all messages
    for msg in messages:
        lines.insert(insert_idx, f"- {msg}")
        insert_idx += 1

    new_content = "\n".join(lines)
    if not new_content.endswith("\n"):
        new_content += "\n"

    post["modified"] = datetime.now().strftime(DATE_TIME)
    post.content = new_content

    with open(backlog_path, "wb") as f:
        frontmatter.dump(post, f, sort_keys=False)

    # 4. Delete messages from Telegram (mark as read)
    # Use offset to acknowledge updates
    if update_ids:
        last_update_id = max(update_ids)
        try:
            offset_url = f"{base_url}/getUpdates?offset={last_update_id + 1}"
            request.urlopen(offset_url).read()
        except error.URLError:
            # Non-fatal: messages were saved, just not cleared from Telegram
            click.echo(
                click.style(
                    "Warning: Messages saved but couldn't clear from Telegram",
                    fg="yellow",
                ),
                err=True,
            )

    return len(messages)
