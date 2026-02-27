-- KayaPure Commerce OS - Initial Database Schema Migration
-- Version: 001
-- Description: Creates core tables for SKUs, daily metrics, checkpoints, VM audit trail, and action proposals

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Table: skus
-- Tracks product inventory, costs, and pricing
-- ============================================
CREATE TABLE IF NOT EXISTS skus (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sku_code VARCHAR(50) UNIQUE NOT NULL,
    unit_cogs FLOAT NOT NULL,
    lab_testing_cost FLOAT DEFAULT 0.0,
    current_stock INTEGER DEFAULT 0,
    daily_sales_velocity FLOAT DEFAULT 0.0,
    current_price FLOAT DEFAULT 0.0,
    competitor_price FLOAT,
    shipping_eta_days INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Table: daily_metrics
-- Daily P&L and business performance data
-- ============================================
CREATE TABLE IF NOT EXISTS daily_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revenue FLOAT DEFAULT 0.0,
    ad_spend FLOAT DEFAULT 0.0,
    shipping_cost FLOAT DEFAULT 0.0,
    cogs_total FLOAT DEFAULT 0.0,
    net_profit FLOAT DEFAULT 0.0,
    margin_percent FLOAT DEFAULT 0.0,
    orders_count INTEGER DEFAULT 0,
    channel VARCHAR(50) DEFAULT 'shopify'
);

-- ============================================
-- Table: checkpoints
-- LangGraph state persistence
-- ============================================
CREATE TABLE IF NOT EXISTS checkpoints (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    checkpoint_id VARCHAR(100) NOT NULL,
    parent_checkpoint_id VARCHAR(100),
    checkpoint_data JSONB NOT NULL,
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_checkpoint ON checkpoints(checkpoint_id);

-- ============================================
-- Table: action_proposals
-- Agent-proposed actions awaiting human approval
-- ============================================
CREATE TABLE IF NOT EXISTS action_proposals (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action_type VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    reasoning TEXT,
    parameters JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'medium',
    sku_id INTEGER REFERENCES skus(id),
    result JSONB,
    vm_session_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON action_proposals(status);

-- ============================================
-- Table: vm_audit_trail
-- Logs every Firecracker microVM session
-- ============================================
CREATE TABLE IF NOT EXISTS vm_audit_trail (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    action_proposal_id INTEGER REFERENCES action_proposals(id),
    vm_boot_time_ms INTEGER DEFAULT 0,
    payload_hash VARCHAR(64),
    code_executed TEXT,
    execution_result JSONB,
    status VARCHAR(20) DEFAULT 'booting',
    hardware_signature VARCHAR(256),
    error_log TEXT
);

CREATE INDEX IF NOT EXISTS idx_vm_audit_session ON vm_audit_trail(session_id);

-- ============================================
-- Seed Data: Sample SKUs for KayaPure products
-- ============================================
INSERT INTO skus (name, sku_code, unit_cogs, lab_testing_cost, current_stock, daily_sales_velocity, current_price, competitor_price, shipping_eta_days) VALUES
    ('KayaPure Organic Turmeric Capsules', 'KP-TUR-001', 3.50, 0.75, 450, 32.0, 24.99, 22.99, 21),
    ('KayaPure Ashwagandha Extract', 'KP-ASH-002', 4.20, 1.00, 120, 18.0, 29.99, 27.99, 28),
    ('KayaPure Vitamin D3+K2', 'KP-VDK-003', 2.80, 0.50, 800, 45.0, 19.99, 18.49, 14),
    ('KayaPure Omega-3 Fish Oil', 'KP-OMG-004', 5.10, 1.20, 200, 25.0, 34.99, 32.99, 35),
    ('KayaPure Probiotics 50B CFU', 'KP-PRO-005', 6.00, 1.50, 350, 20.0, 39.99, 37.99, 18),
    ('KayaPure Magnesium Glycinate', 'KP-MAG-006', 3.00, 0.60, 600, 28.0, 22.99, 21.49, 10),
    ('KayaPure Collagen Peptides', 'KP-COL-007', 7.50, 2.00, 90, 15.0, 44.99, 42.99, 42),
    ('KayaPure Black Seed Oil', 'KP-BSO-008', 4.80, 0.80, 280, 12.0, 27.99, 26.49, 16)
ON CONFLICT (sku_code) DO NOTHING;

-- ============================================
-- Seed Data: Sample daily metrics (last 7 days)
-- ============================================
INSERT INTO daily_metrics (timestamp, revenue, ad_spend, shipping_cost, cogs_total, net_profit, margin_percent, orders_count, channel) VALUES
    (CURRENT_TIMESTAMP - INTERVAL '7 days', 4250.00, 850.00, 425.00, 1275.00, 1700.00, 40.0, 142, 'shopify'),
    (CURRENT_TIMESTAMP - INTERVAL '6 days', 3890.00, 780.00, 389.00, 1167.00, 1554.00, 39.9, 130, 'shopify'),
    (CURRENT_TIMESTAMP - INTERVAL '5 days', 5120.00, 1024.00, 512.00, 1536.00, 2048.00, 40.0, 171, 'shopify'),
    (CURRENT_TIMESTAMP - INTERVAL '4 days', 4680.00, 936.00, 468.00, 1404.00, 1872.00, 40.0, 156, 'shopify'),
    (CURRENT_TIMESTAMP - INTERVAL '3 days', 3200.00, 640.00, 320.00, 960.00, 1280.00, 40.0, 107, 'amazon'),
    (CURRENT_TIMESTAMP - INTERVAL '2 days', 5500.00, 1100.00, 550.00, 1650.00, 2200.00, 40.0, 183, 'shopify'),
    (CURRENT_TIMESTAMP - INTERVAL '1 day', 4900.00, 980.00, 490.00, 1470.00, 1960.00, 40.0, 163, 'shopify');
