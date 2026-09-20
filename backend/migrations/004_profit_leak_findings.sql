-- KayaPure Commerce OS — Profit leak analysis runs and findings
-- Version: 004

CREATE TABLE IF NOT EXISTS profit_leak_analysis_runs (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(100) NOT NULL DEFAULT '',
    account_name VARCHAR(255) NOT NULL DEFAULT '',
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    analysis_type VARCHAR(50) NOT NULL DEFAULT 'profit_leak_scan',
    prompt_version VARCHAR(50),
    model_name VARCHAR(100),
    input_data_hash VARCHAR(64),
    status VARCHAR(30) NOT NULL DEFAULT 'completed',
    summary_json JSONB NOT NULL DEFAULT '{}',
    executive_summary TEXT,
    scan_params_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pl_runs_account_period
    ON profit_leak_analysis_runs (account_id, period_start, period_end, created_at DESC);

CREATE TABLE IF NOT EXISTS profit_leak_findings (
    id VARCHAR(36) PRIMARY KEY,
    analysis_run_id INTEGER NOT NULL REFERENCES profit_leak_analysis_runs(id) ON DELETE CASCADE,
    account_id VARCHAR(100) NOT NULL DEFAULT '',
    account_name VARCHAR(255) NOT NULL DEFAULT '',
    category VARCHAR(80) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    diagnosis TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    llm_explanation TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    estimated_impact_min DOUBLE PRECISION NOT NULL DEFAULT 0,
    estimated_impact_max DOUBLE PRECISION NOT NULL DEFAULT 0,
    entity_type VARCHAR(40) NOT NULL DEFAULT '',
    entity_id VARCHAR(100) NOT NULL DEFAULT '',
    entity_name VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    structured_output JSONB NOT NULL DEFAULT '{}',
    experiment_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pl_findings_run
    ON profit_leak_findings (analysis_run_id, estimated_impact_max DESC);

CREATE INDEX IF NOT EXISTS idx_pl_findings_status
    ON profit_leak_findings (status, created_at DESC);

CREATE TABLE IF NOT EXISTS profit_leak_finding_evidence (
    id SERIAL PRIMARY KEY,
    finding_id VARCHAR(36) NOT NULL REFERENCES profit_leak_findings(id) ON DELETE CASCADE,
    evidence_type VARCHAR(40) NOT NULL DEFAULT 'metric',
    metric_name VARCHAR(80) NOT NULL,
    observed_value TEXT,
    comparison_value TEXT,
    comparison_label VARCHAR(120),
    entity_type VARCHAR(40),
    entity_id VARCHAR(100),
    evidence_json JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pl_evidence_finding
    ON profit_leak_finding_evidence (finding_id);
