-- =============================================================================
-- @akalin/proxy_module - Bağımsız PostgreSQL Veritabanı Şeması (akalin_proxy_db)
-- Tüm projeler (ThinkPort API, Webakus ERP, Studio Live vb.) tarafından ortak
-- kullanılan merkezi Proxy Havuzu, Dinamik Tarayıcı Oturumları ve Telemetri Şeması.
-- =============================================================================

CREATE TABLE IF NOT EXISTS proxy_nodes (
    id TEXT PRIMARY KEY,
    protocol TEXT NOT NULL DEFAULT 'socks5',
    endpoint TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL DEFAULT 'TR',
    city TEXT NOT NULL DEFAULT '',
    proxy_type TEXT NOT NULL DEFAULT 'residential',
    provider TEXT NOT NULL DEFAULT 'Custom Node',
    latency_ms INTEGER NOT NULL DEFAULT 45,
    status TEXT NOT NULL DEFAULT 'active',
    fails INTEGER NOT NULL DEFAULT 0,
    last_checked_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_proxy_nodes_status_latency
    ON proxy_nodes(status, latency_ms ASC);

CREATE INDEX IF NOT EXISTS idx_proxy_nodes_protocol_country
    ON proxy_nodes(protocol, country);

CREATE TABLE IF NOT EXISTS browser_sessions (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    account TEXT NOT NULL DEFAULT '',
    proxy TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'idle',
    requests_served INTEGER NOT NULL DEFAULT 0,
    is_dynamic INTEGER NOT NULL DEFAULT 0,
    idle_ttl_sec INTEGER NOT NULL DEFAULT 300,
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_browser_sessions_provider_status
    ON browser_sessions(provider, status);

CREATE TABLE IF NOT EXISTS pool_metrics_snapshots (
    id TEXT PRIMARY KEY,
    timestamp_iso TEXT NOT NULL,
    time_label TEXT NOT NULL,
    total_sessions INTEGER NOT NULL DEFAULT 0,
    active_busy_sessions INTEGER NOT NULL DEFAULT 0,
    idle_sessions INTEGER NOT NULL DEFAULT 0,
    warm_sessions INTEGER NOT NULL DEFAULT 0,
    dynamic_sessions INTEGER NOT NULL DEFAULT 0,
    max_capacity INTEGER NOT NULL DEFAULT 16,
    active_proxies INTEGER NOT NULL DEFAULT 0,
    cooldown_proxies INTEGER NOT NULL DEFAULT 0,
    avg_proxy_latency_ms INTEGER NOT NULL DEFAULT 0,
    requests_per_min INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pool_metrics_snapshots_ts
    ON pool_metrics_snapshots(timestamp_iso DESC);

CREATE TABLE IF NOT EXISTS pool_scaling_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    session_id TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    proxy_endpoint TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    total_sessions_after INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pool_scaling_events_created
    ON pool_scaling_events(created_at DESC);

CREATE TABLE IF NOT EXISTS proxy_pool_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT ''
);
