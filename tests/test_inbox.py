from urllib import request, error


# TODO
def test_telegram_connection(bot_token: str):
    """Test Telegram bot connection and show bot info.

    Args:
        bot_token: Telegram bot API token

    Raises:
        click.ClickException: If API call fails
    """
    base_url = f"https://api.telegram.org/bot{bot_token}"

    # Get bot info
    try:
        with request.urlopen(f"{base_url}/getMe") as response:
            data = json.loads(response.read())

        if data.get("ok"):
            bot_info = data.get("result", {})
            click.echo(click.style("✓ Bot connection successful", fg="green"))
            click.echo(f"  Bot name: {bot_info.get('first_name')}")
            click.echo(f"  Username: @{bot_info.get('username')}")
            click.echo()
        else:
            raise click.ClickException(f"Bot error: {data.get('description')}")

        # Check for updates
        with request.urlopen(f"{base_url}/getUpdates") as response:
            data = json.loads(response.read())

        if data.get("ok"):
            updates = data.get("result", [])
            click.echo(f"Pending messages: {len(updates)}")
            if updates:
                click.echo("\nMessages:")
                for update in updates:
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    from_user = msg.get("from", {}).get("first_name", "Unknown")
                    click.echo(f"  - {from_user}: {text}")
            else:
                click.echo(click.style("\nNo messages found.", fg="yellow"))
                click.echo("Make sure you:")
                click.echo("  1. Started your bot (send /start)")
                click.echo("  2. Sent at least one message to it")
    except error.URLError as e:
        raise click.ClickException(f"Connection failed: {e}")
