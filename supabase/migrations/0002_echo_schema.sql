-- Echo schema for reply publishing (SPEC-09)
CREATE SCHEMA IF NOT EXISTS echo;

-- Authors we interact with
CREATE TABLE echo.authors (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    handle text NOT NULL UNIQUE,
    times_replied_to integer NOT NULL DEFAULT 0,
    last_replied_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Tracked tweets
CREATE TABLE echo.tweets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tweet_id text NOT NULL UNIQUE,
    tweet_url text NOT NULL,
    author_handle text NOT NULL REFERENCES echo.authors(handle),
    status text NOT NULL DEFAULT 'pending',
    discovered_at timestamptz NOT NULL DEFAULT now(),
    replied_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Voice profiles (referenced by replies)
CREATE TABLE IF NOT EXISTS echo.voice_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    version text NOT NULL,
    active boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Posted replies
CREATE TABLE echo.replies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tweet_id text NOT NULL,
    reply_id text,
    reply_url text,
    reply_text text NOT NULL,
    strategy text NOT NULL,
    was_edited boolean NOT NULL DEFAULT false,
    original_text text,
    voice_profile_version text,
    time_to_reply_seconds integer,
    posted_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_echo_replies_tweet_id ON echo.replies(tweet_id);
CREATE INDEX idx_echo_tweets_status ON echo.tweets(status);
CREATE INDEX idx_echo_tweets_tweet_id ON echo.tweets(tweet_id);
CREATE INDEX idx_echo_authors_handle ON echo.authors(handle);

-- RLS policies (same permissive style as public schema)
ALTER TABLE echo.authors ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.tweets ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE echo.voice_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_echo_authors" ON echo.authors FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_echo_tweets" ON echo.tweets FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_echo_replies" ON echo.replies FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_echo_voice_profiles" ON echo.voice_profiles FOR ALL USING (true) WITH CHECK (true);
