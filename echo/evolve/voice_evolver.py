"""Phase 4b: Optionally evolve voice profile when performance declines."""

from __future__ import annotations

import asyncpg

from echo.evolve.analyser import AnalysisResult


async def get_thirty_day_avg(conn: asyncpg.Connection) -> float:
    """Fetch 30-day rolling average engagement score from daily digests."""
    row = await conn.fetchrow(
        """
        SELECT AVG(avg_engagement_score) AS avg_score
        FROM echo.daily_digests
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        """
    )
    return float(row["avg_score"]) if row and row["avg_score"] else 0.0


async def maybe_evolve_voice(
    conn: asyncpg.Connection,
    analysis: AnalysisResult,
    thirty_day_avg: float,
) -> bool:
    """Re-run voice analysis if performance is declining (>20% below 30-day avg)."""
    if thirty_day_avg <= 0:
        return False  # No historical data yet

    if analysis.avg_engagement_score > thirty_day_avg * 0.8:
        return False  # Performance is fine, skip

    # Re-use existing voice analysis machinery with recent top/poor performers
    top_texts = [r.reply_text for r in analysis.top_performers]
    poor_texts = [r.reply_text for r in analysis.poor_performers]

    if not top_texts:
        return False  # Need some top performers to learn from

    from echo.voice.analyser import analyse_voice

    new_profile = await analyse_voice(
        all_tweets=[{"content": t} for t in top_texts + poor_texts],
        top_tweets=[{"content": t} for t in top_texts],
    )

    from echo.voice.profile import create_new_version

    await create_new_version(
        profile=new_profile,
        source="daily_refinement",
        notes=(
            f"Auto-evolved: avg score {analysis.avg_engagement_score:.2f} "
            f"vs 30d avg {thirty_day_avg:.2f}"
        ),
        tweet_corpus_size=len(top_texts) + len(poor_texts),
    )
    return True
