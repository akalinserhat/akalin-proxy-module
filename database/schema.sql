-- =============================================================================
-- @akalin/proxy_module - Bağımsız PostgreSQL Veritabanı Şeması (akalin_proxy_db)
-- Tüm projeler (ThinkPort API, Webakus ERP, Studio Live vb.) tarafından ortak
-- kullanılan merkezi Proxy Havuzu, Dinamik Tarayıcı Oturumları ve Telemetri Şeması.
-- =============================================================================

CREATE TABLE proxy_nodes (
    id VARCHAR(64) PRIMARY KEY,
    protocol VARCHAR(16) NOT NULL DEFAULT 'socks5',
    endpoint VARCHAR(255) NOT NULL UNIQUE,
    country VARCHAR(8) NOT NULL DEFAULT 'TR',
    city VARCHAR(120) NOT NULL DEFAULT '',
    proxy_type VARCHAR(32) NOT NULL DEFAULT 'residential',
    provider VARCHAR(120) NOT NULL DEFAULT 'Custom Node',
    latency_ms INT NOT NULL DEFAULT 45,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    fails INT NOT NULL DEFAULT 0,
    last_checked_at VARCHAR(64) NOT NULL DEFAULT '',
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL
);

CREATE INDEX idx_proxy_nodes_status_latency
    ON proxy_nodes(status, latency_ms ASC);

CREATE INDEX idx_proxy_nodes_protocol_country
    ON proxy_nodes(protocol, country);

CREATE TABLE browser_sessions (
    id VARCHAR(64) PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    account VARCHAR(255) NOT NULL DEFAULT '',
    proxy VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'idle',
    requests_served INT NOT NULL DEFAULT 0,
    is_dynamic INT NOT NULL DEFAULT 0,
    idle_ttl_sec INT NOT NULL DEFAULT 300,
    created_at VARCHAR(64) NOT NULL,
    last_active_at VARCHAR(64) NOT NULL
);

CREATE INDEX idx_browser_sessions_provider_status
    ON browser_sessions(provider, status);

CREATE TABLE pool_metrics_snapshots (
    id VARCHAR(64) PRIMARY KEY,
    timestamp_iso VARCHAR(64) NOT NULL,
    time_label VARCHAR(32) NOT NULL,
    total_sessions INT NOT NULL DEFAULT 0,
    active_busy_sessions INT NOT NULL DEFAULT 0,
    idle_sessions INT NOT NULL DEFAULT 0,
    warm_sessions INT NOT NULL DEFAULT 0,
    dynamic_sessions INT NOT NULL DEFAULT 0,
    max_capacity INT NOT NULL DEFAULT 16,
    active_proxies INT NOT NULL DEFAULT 0,
    cooldown_proxies INT NOT NULL DEFAULT 0,
    avg_proxy_latency_ms INT NOT NULL DEFAULT 0,
    requests_per_min INT NOT NULL DEFAULT 0
);

CREATE INDEX idx_pool_metrics_snapshots_ts
    ON pool_metrics_snapshots(timestamp_iso DESC);

CREATE TABLE pool_scaling_events (
    id VARCHAR(64) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL DEFAULT '',
    provider VARCHAR(64) NOT NULL DEFAULT '',
    proxy_endpoint VARCHAR(255) NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    total_sessions_after INT NOT NULL DEFAULT 0,
    created_at VARCHAR(64) NOT NULL
);

CREATE INDEX idx_pool_scaling_events_created
    ON pool_scaling_events(created_at DESC);

CREATE TABLE proxy_pool_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value TEXT NOT NULL DEFAULT '{}',
    updated_at VARCHAR(64) NOT NULL DEFAULT ''
);
