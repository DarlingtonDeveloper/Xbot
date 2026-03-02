-- Echo schema for analytics collector (SPEC-11)
CREATE SCHEMA IF NOT EXISTS echo;

-- Replies table: stores posted replies and their latest metrics
CREATE TABLE echo.replies (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reply_id        text UNIQUE,                    -- X tweet ID
    reply_url       text,
    reply_text      text,
    posted_at       timestamp with time zone,
    impressions     integer DEFAULT 0,
    likes           integer DEFAULT 0,
    retweets        integer DEFAULT 0,
    replies_count   integer DEFAULT 0,
    bookmarks       integer DEFAULT 0,
    profile_clicks  integer DEFAULT 0,
    metrics_updated_at timestamp with time zone,
    created_at      timestamp with time zone DEFAULT now() NOT NULL,
    updated_at      timestamp with time zone DEFAULT now() NOT NULL
);

CREATE INDEX idx_replies_posted_at ON echo.replies (posted_at DESC);
CREATE INDEX idx_replies_metrics_due ON echo.replies (posted_at, metrics_updated_at)
    WHERE posted_at IS NOT NULL AND reply_url IS NOT NULL;

-- Time-series metric snapshots
CREATE TABLE echo.reply_metrics (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reply_id        text NOT NULL REFERENCES echo.replies(reply_id) ON DELETE CASCADE,
    impressions     integer DEFAULT 0,
    likes           integer DEFAULT 0,
    retweets        integer DEFAULT 0,
    replies         integer DEFAULT 0,
    bookmarks       integer DEFAULT 0,
    profile_clicks  integer DEFAULT 0,
    scraped_at      timestamp with time zone DEFAULT now() NOT NULL
);

CREATE INDEX idx_reply_metrics_reply_id ON echo.reply_metrics (reply_id, scraped_at DESC);

-- Daily follower count snapshots
CREATE TABLE echo.follower_snapshots (
    date            date PRIMARY KEY,
    follower_count  integer NOT NULL,
    delta           integer DEFAULT 0
);

-- CSV import tracking for dedup
CREATE TABLE echo.analytics_imports (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        text NOT NULL,
    rows_imported   integer DEFAULT 0,
    rows_unmatched  integer DEFAULT 0,
    date_range_start timestamp with time zone,
    date_range_end  timestamp with time zone,
    imported_at     timestamp with time zone DEFAULT now() NOT NULL
);

-- RLS policies (self-hosted, allow all)
ALTER TABLE echo.replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.reply_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.follower_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.analytics_imports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all" ON echo.replies FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON echo.reply_metrics FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON echo.follower_snapshots FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all" ON echo.analytics_imports FOR ALL USING (true) WITH CHECK (true);
