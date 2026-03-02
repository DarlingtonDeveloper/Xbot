CREATE SCHEMA IF NOT EXISTS echo;

CREATE TABLE echo.authors (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "handle" text NOT NULL UNIQUE,
    "display_name" text,
    "bio" text,
    "followers" integer DEFAULT 0 NOT NULL,
    "following" integer DEFAULT 0 NOT NULL,
    "verified" boolean DEFAULT false NOT NULL,
    "website" text,
    "join_date" timestamp with time zone,
    "avg_engagement_rate" double precision DEFAULT 0.0 NOT NULL,
    "posting_frequency" double precision DEFAULT 0.0 NOT NULL,
    "enrichment_brief" text,
    "enrichment_updated" timestamp with time zone,
    "times_replied_to" integer DEFAULT 0 NOT NULL,
    "last_replied_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT now() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE echo.authors ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_authors" ON echo.authors FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX "idx_authors_handle" ON echo.authors USING btree ("handle");
CREATE INDEX "idx_authors_enrichment_updated" ON echo.authors USING btree ("enrichment_updated");
