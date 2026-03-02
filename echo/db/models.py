from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class GeneratedReply:
    slot: int
    strategy: str
    text: str
    original_text: Optional[str] = None


@dataclass
class Tweet:
    tweet_id: str
    author_handle: str
    author_followers: int
    author_verified: bool
    content: str
    likes_t0: int
    replies_t0: int
    retweets_t0: int
    virality_score: float
    status: str
    tweet_created_at: datetime
    discovered_at: datetime


@dataclass
class Candidate:
    tweet: Tweet
    generated_replies: list[GeneratedReply] = field(default_factory=list)


@dataclass
class Reply:
    reply_id: str
    tweet_id: str
    reply_text: str
    strategy: str
    was_edited: bool
    original_text: Optional[str]
    impressions: Optional[int]
    likes: Optional[int]
    follower_delta: Optional[int]
    posted_at: datetime


@dataclass
class SessionStats:
    queue_depth: int
    posted_today: int
    avg_score: Optional[float]
    follower_delta: int


@dataclass
class PostedReply:
    reply_text: str
    strategy: str
    impressions: Optional[int]
    likes: Optional[int]
    posted_at: datetime
    author_handle: str
