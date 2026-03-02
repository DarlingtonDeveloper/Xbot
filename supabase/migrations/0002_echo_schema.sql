-- Echo schema: tweet candidates and replies for the CLI interface

CREATE SCHEMA IF NOT EXISTS echo;

CREATE TABLE echo.tweets (
    tweet_id          text PRIMARY KEY,
    author_handle     text NOT NULL,
    author_followers  integer NOT NULL DEFAULT 0,
    author_verified   boolean NOT NULL DEFAULT false,
    content           text NOT NULL,
    likes_t0          integer NOT NULL DEFAULT 0,
    replies_t0        integer NOT NULL DEFAULT 0,
    retweets_t0       integer NOT NULL DEFAULT 0,
    virality_score    real NOT NULL DEFAULT 0,
    status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'presented', 'replied', 'skipped')),
    tweet_created_at  timestamp with time zone NOT NULL DEFAULT now(),
    discovered_at     timestamp with time zone NOT NULL DEFAULT now(),
    presented_at      timestamp with time zone,
    resolved_at       timestamp with time zone
);

CREATE INDEX idx_echo_tweets_status ON echo.tweets (status);
CREATE INDEX idx_echo_tweets_score ON echo.tweets (virality_score DESC);
CREATE INDEX idx_echo_tweets_discovered ON echo.tweets (discovered_at);

CREATE TABLE echo.replies (
    reply_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tweet_id          text NOT NULL REFERENCES echo.tweets(tweet_id) ON DELETE CASCADE,
    reply_text        text NOT NULL,
    strategy          text NOT NULL,
    was_edited        boolean NOT NULL DEFAULT false,
    original_text     text,
    impressions       integer,
    likes             integer,
    follower_delta    integer,
    posted_at         timestamp with time zone NOT NULL DEFAULT now()
);

CREATE INDEX idx_echo_replies_tweet ON echo.replies (tweet_id);
CREATE INDEX idx_echo_replies_posted ON echo.replies (posted_at);

CREATE TABLE echo.generated_replies (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tweet_id          text NOT NULL REFERENCES echo.tweets(tweet_id) ON DELETE CASCADE,
    slot              integer NOT NULL CHECK (slot BETWEEN 1 AND 5),
    strategy          text NOT NULL,
    text              text NOT NULL,
    created_at        timestamp with time zone NOT NULL DEFAULT now(),
    UNIQUE (tweet_id, slot)
);

CREATE INDEX idx_echo_generated_tweet ON echo.generated_replies (tweet_id);
