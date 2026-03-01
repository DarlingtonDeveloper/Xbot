ALTER TABLE configs ADD COLUMN embedding vector(1536);
ALTER TABLE configs ADD COLUMN visit_count integer DEFAULT 0 NOT NULL;

CREATE INDEX "idx_configs_embedding" ON "configs" USING hnsw ("embedding" vector_cosine_ops);
