-- KayaPure Commerce OS — Apify Actor runs and review analysis
-- Version: 003

CREATE TABLE IF NOT EXISTS apify_actor_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) UNIQUE NOT NULL,
    actor_id VARCHAR(200) NOT NULL DEFAULT '',
    dataset_id VARCHAR(100) NOT NULL DEFAULT '',
    status VARCHAR(40) NOT NULL DEFAULT '',
    source VARCHAR(40) NOT NULL DEFAULT 'manual',
    mode VARCHAR(40) NOT NULL DEFAULT 'reviews',
    label VARCHAR(500) NOT NULL DEFAULT '',
    product_title VARCHAR(500),
    product_asin VARCHAR(20),
    product_url TEXT,
    raw_json JSONB NOT NULL,
    snapshot_json JSONB,
    analysis_json JSONB,
    analysis_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_apify_actor_runs_updated
    ON apify_actor_runs (updated_at DESC);
