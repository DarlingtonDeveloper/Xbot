-- Echo schema: tables, indexes, and RLS
-- Isolated from Ami's public schema tables

CREATE SCHEMA IF NOT EXISTS echo;

-- Safety net (already enabled in 0001_init_schema.sql)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- 1. tweets — Discovered tweets that passed hard filters
-- ============================================================
CREATE TABLE echo.tweets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tweet_id            TEXT UNIQUE NOT NULL,
    tweet_url           TEXT NOT NULL,
    author_handle       TEXT NOT NULL,
    author_name         TEXT,
    content             TEXT NOT NULL,
    is_thread           BOOLEAN DEFAULT FALSE,
    has_media           BOOLEAN DEFAULT FALSE,
    is_quote_tweet      BOOLEAN DEFAULT FALSE,

    -- Author snapshot at discovery time
    author_followers    INTEGER,
    author_following    INTEGER,
    author_verified     BOOLEAN DEFAULT FALSE,

    -- Metrics at discovery (T+0)
    likes_t0            INTEGER DEFAULT 0,
    retweets_t0         INTEGER DEFAULT 0,
    replies_t0          INTEGER DEFAULT 0,
    bookmarks_t0        INTEGER DEFAULT 0,
    views_t0            BIGINT DEFAULT 0,

    -- Scoring
    virality_score      REAL,
    author_score        REAL,
    content_score       REAL,
    momentum_score      REAL,
    recency_multiplier  REAL,
    source              TEXT CHECK (source IN ('watchlist', 'keyword_search')),
    matched_keywords    TEXT[],

    -- Embedding for semantic similarity
    content_embedding   vector(1536),

    -- Lifecycle
    status              TEXT DEFAULT 'queued'
                        CHECK (status IN ('queued', 'presented', 'replied', 'skipped', 'expired')),
    discovered_at       TIMESTAMPTZ DEFAULT NOW(),
    tweet_created_at    TIMESTAMPTZ,
    presented_at        TIMESTAMPTZ,
    replied_at          TIMESTAMPTZ,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tweets_status ON echo.tweets(status);
CREATE INDEX idx_tweets_virality ON echo.tweets(virality_score DESC);
CREATE INDEX idx_tweets_discovered ON echo.tweets(discovered_at DESC);
CREATE INDEX idx_tweets_author ON echo.tweets(author_handle);
CREATE INDEX idx_tweets_tweet_id ON echo.tweets(tweet_id);

-- ============================================================
-- 2. tweet_metrics — Time-series metric snapshots for velocity
-- ============================================================
CREATE TABLE echo.tweet_metrics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tweet_id    TEXT NOT NULL REFERENCES echo.tweets(tweet_id),
    likes       INTEGER DEFAULT 0,
    retweets    INTEGER DEFAULT 0,
    replies     INTEGER DEFAULT 0,
    bookmarks   INTEGER DEFAULT 0,
    views       BIGINT DEFAULT 0,
    scraped_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tweet_metrics_tweet ON echo.tweet_metrics(tweet_id, scraped_at);

-- ============================================================
-- 3. replies — Every reply Echo posts
-- ============================================================
CREATE TABLE echo.replies (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tweet_id                TEXT NOT NULL REFERENCES echo.tweets(tweet_id),
    reply_id                TEXT UNIQUE,
    reply_url               TEXT,
    reply_text              TEXT NOT NULL,
    strategy                TEXT NOT NULL
                            CHECK (strategy IN ('contrarian', 'experience', 'additive', 'question', 'pattern_interrupt')),
    was_edited              BOOLEAN DEFAULT FALSE,
    original_text           TEXT,
    voice_profile_version   TEXT,

    -- Performance metrics (updated by Analyse phase)
    impressions             BIGINT,
    likes                   INTEGER,
    retweets                INTEGER,
    replies_count           INTEGER,
    bookmarks               INTEGER,
    profile_clicks          INTEGER,
    follower_delta          INTEGER,

    -- Timing
    time_to_reply_seconds   INTEGER,
    posted_at               TIMESTAMPTZ,
    metrics_updated_at      TIMESTAMPTZ,

    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_replies_tweet ON echo.replies(tweet_id);
CREATE INDEX idx_replies_strategy ON echo.replies(strategy);
CREATE INDEX idx_replies_posted ON echo.replies(posted_at DESC);
CREATE INDEX idx_replies_impressions ON echo.replies(impressions DESC NULLS LAST);

-- ============================================================
-- 4. reply_metrics — Time-series metrics for replies (T+1h, T+6h, T+24h)
-- ============================================================
CREATE TABLE echo.reply_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reply_id        TEXT NOT NULL REFERENCES echo.replies(reply_id),
    impressions     BIGINT DEFAULT 0,
    likes           INTEGER DEFAULT 0,
    retweets        INTEGER DEFAULT 0,
    replies         INTEGER DEFAULT 0,
    bookmarks       INTEGER DEFAULT 0,
    profile_clicks  INTEGER DEFAULT 0,
    scraped_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reply_metrics_reply ON echo.reply_metrics(reply_id, scraped_at);

-- ============================================================
-- 5. authors — Cached author profiles
-- ============================================================
CREATE TABLE echo.authors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    handle              TEXT UNIQUE NOT NULL,
    display_name        TEXT,
    bio                 TEXT,
    followers           INTEGER,
    following           INTEGER,
    verified            BOOLEAN DEFAULT FALSE,
    website             TEXT,
    join_date           TEXT,
    avg_engagement_rate REAL,
    posting_frequency   REAL,

    -- LLM-generated enrichment
    enrichment_brief    TEXT,
    enrichment_updated  TIMESTAMPTZ,

    -- Interaction history
    times_replied_to    INTEGER DEFAULT 0,
    last_replied_at     TIMESTAMPTZ,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_authors_handle ON echo.authors(handle);
CREATE INDEX idx_authors_updated ON echo.authors(updated_at);

-- ============================================================
-- 6. voice_profiles — Version-controlled voice profile iterations
-- ============================================================
CREATE TABLE echo.voice_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version             TEXT NOT NULL UNIQUE,
    profile_json        JSONB NOT NULL,
    source              TEXT CHECK (source IN ('bootstrap', 'daily_refinement', 'manual')),
    tweet_corpus_size   INTEGER,
    notes               TEXT,
    is_active           BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_active ON echo.voice_profiles(is_active) WHERE is_active = TRUE;

-- ============================================================
-- 7. strategy_scores — Daily strategy performance tracking
-- ============================================================
CREATE TABLE echo.strategy_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date            DATE NOT NULL,
    strategy        TEXT NOT NULL
                    CHECK (strategy IN ('contrarian', 'experience', 'additive', 'question', 'pattern_interrupt')),
    replies_count   INTEGER DEFAULT 0,
    avg_impressions REAL,
    avg_likes       REAL,
    avg_profile_clicks REAL,
    win_rate        REAL,
    rolling_7d_win_rate REAL,

    UNIQUE(date, strategy)
);

CREATE INDEX idx_strategy_date ON echo.strategy_scores(date DESC);

-- ============================================================
-- 8. model_weights — Versioned scoring model weights
-- ============================================================
CREATE TABLE echo.model_weights (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version         TEXT NOT NULL UNIQUE,
    weights_json    JSONB NOT NULL,
    accuracy_score  REAL,
    is_active       BOOLEAN DEFAULT FALSE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_weights_active ON echo.model_weights(is_active) WHERE is_active = TRUE;

-- ============================================================
-- 9. daily_digests — Stored end-of-day summaries
-- ============================================================
CREATE TABLE echo.daily_digests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date                DATE UNIQUE NOT NULL,
    tweets_discovered   INTEGER,
    tweets_presented    INTEGER,
    replies_posted      INTEGER,
    avg_impressions     REAL,
    best_reply_id       TEXT REFERENCES echo.replies(reply_id),
    follower_delta      INTEGER,
    strategy_breakdown  JSONB,
    recommendations     TEXT,
    digest_json         JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 10. analytics_imports — Track CSV imports for deduplication
-- ============================================================
CREATE TABLE echo.analytics_imports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename            TEXT,
    rows_imported       INTEGER,
    date_range_start    DATE,
    date_range_end      DATE,
    imported_at         TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Row-Level Security — enable on ALL echo tables
-- ============================================================
ALTER TABLE echo.tweets ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.tweet_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.reply_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.authors ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.voice_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.strategy_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.model_weights ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.daily_digests ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.analytics_imports ENABLE ROW LEVEL SECURITY;

-- Service-role full access (single-tenant; Echo backend only)
CREATE POLICY service_full_access ON echo.tweets FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.tweet_metrics FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.replies FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.reply_metrics FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.authors FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.voice_profiles FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.strategy_scores FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.model_weights FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.daily_digests FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY service_full_access ON echo.analytics_imports FOR ALL USING (TRUE) WITH CHECK (TRUE);
