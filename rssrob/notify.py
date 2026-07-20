"""Send notifications via Apprise (supports Telegram, Discord, Slack, email, etc.).

Apprise uses URL-based configuration. Examples:
    tgram://bot_token/chat_id        # Telegram
    discord://webhook_id/token       # Discord
    slack://token/a/b/c              # Slack
    mailto://user:pass@smtp_host     # Email via SMTP
    json://localhost                 # HTTP JSON webhook
    gotify://gotify.example.com/token  # Gotify
    ntfys://ntfy.example.com/topic    # ntfy

Usage:
    import apprise

    a = apprise.Apprise()
    a.add("tgram://123456:ABC-DEF/123456789")
    a.notify(title="New update", body="New items found")
"""

import apprise as _apprise


class NotifyError(Exception):
    pass


def send_notification(urls, title: str, body: str, body_html: str = None) -> None:
    """Send a notification to one or more Apprise URLs.

    Args:
        urls: List of Apprise URL strings.
        title: Notification title.
        body: Plain text body.
        body_html: Optional HTML body (not all services support it).
    """
    if not urls:
        return
    a = _apprise.Apprise()
    for url in urls:
        a.add(url)
    kwargs = {"title": title, "body": body}
    if body_html:
        kwargs["body_format"] = _apprise.NotifyFormat.HTML
        kwargs["body"] = body_html
    result = a.notify(**kwargs)
    if not result:
        raise NotifyError("all notification targets failed")
