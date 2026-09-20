-- KayaPure Commerce OS — Reports, action outcomes
-- Version: 002

CREATE TABLE IF NOT EXISTS ads_analysis_reports (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(100) NOT NULL,
    account_name VARCHAR(255) NOT NULL DEFAULT '',
    report_type VARCHAR(50) NOT NULL DEFAULT 'generate',
    days INTEGER NOT NULL DEFAULT 30,
    question TEXT,
    analysis_json JSONB NOT NULL,
    data_snapshot_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ads_reports_account ON ads_analysis_reports(account_id, report_type, created_at DESC);

CREATE TABLE IF NOT EXISTS action_outcomes (
    id SERIAL PRIMARY KEY,
    action_proposal_id INTEGER NOT NULL REFERENCES action_proposals(id) ON DELETE CASCADE,
    outcome_type VARCHAR(50) NOT NULL DEFAULT 'execution',
    success BOOLEAN NOT NULL DEFAULT FALSE,
    metrics_json JSONB,
    notes TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_action_outcomes_proposal ON action_outcomes(action_proposal_id);
