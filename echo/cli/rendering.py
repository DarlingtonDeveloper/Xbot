from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from echo.db.models import Candidate, GeneratedReply, PostedReply, SessionStats

TIER_EMOJI = {"red": "🔴", "yellow": "🟡", "green": "🟢"}

STRATEGY_ICONS = {
    "contrarian": "🔥",
    "experience": "🛠️",
    "additive": "➕",
    "question": "❓",
    "pattern_interrupt": "🎯",
}


def get_tier(score: float) -> str:
    if score >= 80:
        return "red"
    elif score >= 50:
        return "yellow"
    return "green"


def format_age(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def render_tweet(console: Console, candidate: Candidate) -> None:
    tweet = candidate.tweet
    tier = get_tier(tweet.virality_score)
    emoji = TIER_EMOJI[tier]

    header = f"{emoji} ECHO — New candidate (score: {tweet.virality_score:.0f})"

    author_line = f"@{tweet.author_handle} ({tweet.author_followers:,} followers"
    if tweet.author_verified:
        author_line += ", ✓ verified"
    author_line += ")"

    age = format_age(tweet.tweet_created_at)
    metrics = (
        f"📊 {tweet.likes_t0} likes · "
        f"{tweet.replies_t0} replies · "
        f"{tweet.retweets_t0} RTs · "
        f"{age}"
    )

    console.print(Panel(
        f"[bold]{author_line}[/]\n"
        f'"{tweet.content}"\n'
        f"[dim]{metrics}[/]",
        title=header,
        border_style="bright_cyan",
    ))


def render_replies(console: Console, replies: list[GeneratedReply]) -> None:
    console.print("\n[bold]━━━ Your replies ━━━[/]\n")

    for i, reply in enumerate(replies, 1):
        icon = STRATEGY_ICONS.get(reply.strategy, "💬")
        label = reply.strategy.replace("_", " ").title()
        console.print(
            f"[bold][{i}] {icon} {label}[/]\n"
            f'"{reply.text}"\n'
        )


def render_status(console: Console, stats: SessionStats) -> None:
    table = Table(title="Today's Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold")
    table.add_row("Queue depth", str(stats.queue_depth))
    table.add_row("Replies posted", str(stats.posted_today))
    table.add_row(
        "Avg candidate score",
        f"{stats.avg_score:.1f}" if stats.avg_score is not None else "—",
    )
    table.add_row("Follower delta", f"+{stats.follower_delta}")
    console.print(table)


def render_history(console: Console, replies: list[PostedReply]) -> None:
    if not replies:
        console.print("[dim]No replies posted today.[/]")
        return

    for r in replies:
        age = format_age(r.posted_at)
        impressions = str(r.impressions) if r.impressions is not None else "..."
        likes = str(r.likes) if r.likes is not None else "..."
        console.print(
            f"[dim]{age}[/] → @{r.author_handle} [{r.strategy}]\n"
            f'  "{r.reply_text[:80]}{"..." if len(r.reply_text) > 80 else ""}"\n'
            f"  👁 {impressions} · ❤️ {likes}\n"
        )


def render_waiting(console: Console, queue_depth: int, stats: SessionStats) -> None:
    posted = stats.posted_today
    avg = f"avg score {stats.avg_score:.0f}" if stats.avg_score else "no candidates yet"
    delta = f"+{stats.follower_delta} followers" if stats.follower_delta else ""

    parts = [f"{posted} replies posted", avg]
    if delta:
        parts.append(delta)

    console.print(
        f"\n⏳ Watching for candidates... (queue: {queue_depth})\n"
        f"   Today: {' · '.join(parts)}\n"
    )
