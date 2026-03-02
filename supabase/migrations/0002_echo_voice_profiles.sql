CREATE SCHEMA IF NOT EXISTS echo;

CREATE TABLE echo.voice_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version TEXT NOT NULL UNIQUE,
    profile_json JSONB NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('bootstrap', 'daily_refinement', 'manual')),
    tweet_corpus_size INTEGER,
    notes TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Only one profile can be active at a time
CREATE UNIQUE INDEX idx_voice_profiles_active
    ON echo.voice_profiles (is_active)
    WHERE is_active = TRUE;

ALTER TABLE echo.voice_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_voice_profiles" ON echo.voice_profiles FOR ALL USING (true) WITH CHECK (true);
