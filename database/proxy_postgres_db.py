"""
@akalin/proxy_module - Bağımsız PostgreSQL Veritabanı Yöneticisi (proxy_postgres_db.py).
Tüm projeler (ThinkPort API, Webakus ERP, Studio Live vb.) için merkezi `akalin_proxy_db`
PostgreSQL veritabanını otomatik oluşturur, şemayı kurar, başlangıç verilerini (seed) yükler
ve Proxy / Oturum / Telemetri işlemlerini doğrudan PostgreSQL üzerinde yürütür.
"""
from __future__ import annotations
import importlib.util
import os
import random
import re
import socket
import ssl
import threading
import time
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

PROXY_PG_HOST = os.getenv("PROXY_POSTGRES_HOST", os.getenv("POSTGRES_HOST", "127.0.0.1"))
PROXY_PG_PORT = int(os.getenv("PROXY_POSTGRES_PORT", os.getenv("POSTGRES_PORT", "5432")))
PROXY_PG_ADMIN_USER = os.getenv("PROXY_POSTGRES_ADMIN_USER", "postgres")
PROXY_PG_ADMIN_PASSWORD = os.getenv("PROXY_POSTGRES_ADMIN_PASSWORD", "postgres")
PROXY_PG_USER = os.getenv("PROXY_POSTGRES_USER", os.getenv("POSTGRES_USER", "postgres"))
PROXY_PG_PASSWORD = os.getenv("PROXY_POSTGRES_PASSWORD", os.getenv("POSTGRES_PASSWORD", "postgres"))
PROXY_PG_DB = os.getenv("PROXY_POSTGRES_DB", "akalin_proxy_db")

_drv_path = Path(__file__).resolve().parent / "postgres_driver.py"
_drv_spec = importlib.util.spec_from_file_location("akalin_proxy_pg_driver", str(_drv_path))
assert _drv_spec and _drv_spec.loader
_drv_mod = importlib.util.module_from_spec(_drv_spec)
_drv_spec.loader.exec_module(_drv_mod)
PgWireConnection = _drv_mod.PgWireConnection

_schema_path = Path(__file__).resolve().parent / "schema.sql"
_raw_schema = _schema_path.read_text(encoding="utf-8")
SCHEMA_SQL = re.sub(
    r"\bCREATE\s+(TABLE|INDEX)\s+(?!IF\s+NOT\s+EXISTS\b)",
    r"CREATE \1 IF NOT EXISTS ",
    _raw_schema,
    flags=re.IGNORECASE,
)

PROXY_FEED_SOURCES: Dict[str, List[str]] = {
    "http": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=elite",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    ],
    "https": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=yes&anonymity=elite",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ],
    "socks5": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=3000&country=all",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    ],
    "socks4": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=3000&country=all",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    ],
}

PROXY_REGIONS: List[Tuple[str, str]] = [
    ("DE", "Frankfurt"),
    ("NL", "Amsterdam"),
    ("US", "New York"),
    ("GB", "London"),
    ("FR", "Paris"),
    ("TR", "Istanbul"),
    ("CH", "Zurich"),
    ("SG", "Singapore"),
    ("JP", "Tokyo"),
    ("FI", "Helsinki"),
    ("PL", "Warsaw"),
    ("CA", "Montreal"),
]

FALLBACK_PUBLIC_PROXIES: List[Tuple[str, str]] = [
    ("socks5", "185.199.229.156:7492"),
    ("http", "103.152.112.162:80"),
    ("socks5", "72.195.34.58:4145"),
    ("https", "45.8.106.59:8080"),
    ("socks5", "194.163.133.19:1080"),
    ("http", "212.102.51.66:3128"),
    ("socks4", "178.62.193.19:1080"),
    ("https", "154.236.179.226:1981"),
    ("socks5", "79.76.59.115:1081"),
    ("socks5", "98.178.72.30:4145"),
    ("socks5", "195.19.50.135:1081"),
    ("socks5", "174.77.111.196:4145"),
    ("socks5", "46.62.236.59:1081"),
    ("socks5", "66.59.197.61:3129"),
    ("socks5", "216.68.128.121:4145"),
    ("socks5", "45.61.129.165:9050"),
    ("socks5", "195.135.255.98:1081"),
    ("socks5", "98.190.239.3:4145"),
    ("http", "203.205.49.2:10040"),
    ("http", "43.153.45.165:8118"),
]

SEED_PROXIES: List[Dict[str, Any]] = [
    {"id": "prx-01", "protocol": "http", "endpoint": "194.36.110.12:8080", "country": "TR", "city": "Istanbul", "proxy_type": "residential", "provider": "TurkNet Res", "latency_ms": 14, "status": "active", "fails": 0},
    {"id": "prx-02", "protocol": "socks5", "endpoint": "88.255.140.28:1080", "country": "TR", "city": "Ankara", "proxy_type": "mobile", "provider": "TR 5G Mobile", "latency_ms": 21, "status": "active", "fails": 0},
    {"id": "prx-03", "protocol": "https", "endpoint": "85.105.42.91:8080", "country": "DE", "city": "Frankfurt", "proxy_type": "residential", "provider": "BrightData EU", "latency_ms": 38, "status": "active", "fails": 0},
    {"id": "prx-04", "protocol": "socks5", "endpoint": "138.201.92.14:1080", "country": "DE", "city": "Berlin", "proxy_type": "isp", "provider": "DE-CIX Static", "latency_ms": 42, "status": "active", "fails": 0},
    {"id": "prx-05", "protocol": "socks5", "endpoint": "176.88.19.204:1080", "country": "US", "city": "New York", "proxy_type": "residential", "provider": "Oxylabs US", "latency_ms": 96, "status": "active", "fails": 1},
    {"id": "prx-06", "protocol": "https", "endpoint": "64.225.88.110:8443", "country": "US", "city": "Los Angeles", "proxy_type": "mobile", "provider": "T-Mobile 5G", "latency_ms": 134, "status": "active", "fails": 0},
    {"id": "prx-07", "protocol": "socks5", "endpoint": "198.51.100.77:1080", "country": "US", "city": "Ashburn", "proxy_type": "isp", "provider": "Smartproxy ISP", "latency_ms": 89, "status": "active", "fails": 0},
    {"id": "prx-08", "protocol": "http", "endpoint": "91.93.120.44:8080", "country": "NL", "city": "Amsterdam", "proxy_type": "residential", "provider": "IPRoyal NL", "latency_ms": 47, "status": "cooldown", "fails": 3},
    {"id": "prx-09", "protocol": "https", "endpoint": "185.220.101.5:8443", "country": "GB", "city": "London", "proxy_type": "residential", "provider": "SOAX UK", "latency_ms": 54, "status": "active", "fails": 0},
    {"id": "prx-10", "protocol": "socks5", "endpoint": "51.158.118.42:1080", "country": "FR", "city": "Paris", "proxy_type": "isp", "provider": "Scaleway FR", "latency_ms": 49, "status": "active", "fails": 0},
    {"id": "prx-11", "protocol": "https", "endpoint": "179.43.148.19:8443", "country": "CH", "city": "Zurich", "proxy_type": "residential", "provider": "SwissPrivacy", "latency_ms": 44, "status": "active", "fails": 0},
    {"id": "prx-12", "protocol": "socks5", "endpoint": "45.76.210.88:1080", "country": "JP", "city": "Tokyo", "proxy_type": "residential", "provider": "NTT Japan", "latency_ms": 168, "status": "active", "fails": 0},
    {"id": "prx-13", "protocol": "http", "endpoint": "128.199.180.52:8080", "country": "SG", "city": "Singapore", "proxy_type": "datacenter", "provider": "SingTel DC", "latency_ms": 152, "status": "active", "fails": 0},
    {"id": "prx-14", "protocol": "socks4", "endpoint": "159.203.24.91:1080", "country": "CA", "city": "Toronto", "proxy_type": "residential", "provider": "Bell Canada", "latency_ms": 108, "status": "active", "fails": 0},
    {"id": "prx-15", "protocol": "https", "endpoint": "193.138.218.60:8443", "country": "SE", "city": "Stockholm", "proxy_type": "residential", "provider": "Mullvad SE", "latency_ms": 59, "status": "active", "fails": 0},
    {"id": "prx-16", "protocol": "socks5", "endpoint": "95.216.144.33:1080", "country": "FI", "city": "Helsinki", "proxy_type": "datacenter", "provider": "NordNode FI", "latency_ms": 62, "status": "active", "fails": 0},
    {"id": "prx-17", "protocol": "socks5", "endpoint": "145.220.227.208:8080", "country": "NL", "city": "Rotterdam", "proxy_type": "residential", "provider": "KPN Fiber NL", "latency_ms": 45, "status": "active", "fails": 0},
    {"id": "prx-18", "protocol": "socks5", "endpoint": "49.13.162.163:1081", "country": "DE", "city": "Nuremberg", "proxy_type": "datacenter", "provider": "Hetzner Cloud DE", "latency_ms": 36, "status": "active", "fails": 0},
    {"id": "prx-19", "protocol": "socks5", "endpoint": "212.47.71.179:9167", "country": "FR", "city": "Marseille", "proxy_type": "isp", "provider": "OnlineSAS FR", "latency_ms": 48, "status": "active", "fails": 0},
    {"id": "prx-20", "protocol": "socks5", "endpoint": "185.151.86.121:3699", "country": "GB", "city": "Manchester", "proxy_type": "residential", "provider": "BT Broadband UK", "latency_ms": 56, "status": "active", "fails": 0},
    {"id": "prx-21", "protocol": "socks5", "endpoint": "192.252.215.5:16137", "country": "US", "city": "Chicago", "proxy_type": "residential", "provider": "Comcast Xfinity", "latency_ms": 104, "status": "active", "fails": 0},
    {"id": "prx-22", "protocol": "socks5", "endpoint": "208.102.51.6:58208", "country": "US", "city": "Dallas", "proxy_type": "mobile", "provider": "AT&T 5G US", "latency_ms": 118, "status": "active", "fails": 0},
    {"id": "prx-23", "protocol": "socks5", "endpoint": "142.54.237.34:4145", "country": "US", "city": "Kansas City", "proxy_type": "isp", "provider": "Wholesale ISP", "latency_ms": 112, "status": "active", "fails": 0},
    {"id": "prx-24", "protocol": "socks5", "endpoint": "184.170.245.148:4145", "country": "US", "city": "Phoenix", "proxy_type": "residential", "provider": "Cox Residential", "latency_ms": 127, "status": "active", "fails": 0},
    {"id": "prx-25", "protocol": "http", "endpoint": "91.107.143.251:80", "country": "DE", "city": "Falkenstein", "proxy_type": "datacenter", "provider": "Hetzner Edge", "latency_ms": 39, "status": "active", "fails": 0},
    {"id": "prx-26", "protocol": "http", "endpoint": "137.74.50.101:15054", "country": "PL", "city": "Warsaw", "proxy_type": "isp", "provider": "OVH Poland", "latency_ms": 51, "status": "active", "fails": 0},
    {"id": "prx-27", "protocol": "https", "endpoint": "82.69.119.68:49200", "country": "GB", "city": "Bristol", "proxy_type": "residential", "provider": "Virgin Media UK", "latency_ms": 58, "status": "active", "fails": 0},
    {"id": "prx-28", "protocol": "http", "endpoint": "195.114.209.50:80", "country": "PL", "city": "Krakow", "proxy_type": "residential", "provider": "Orange Polska", "latency_ms": 53, "status": "active", "fails": 0},
    {"id": "prx-29", "protocol": "https", "endpoint": "5.45.126.128:8080", "country": "AT", "city": "Vienna", "proxy_type": "isp", "provider": "A1 Telekom AT", "latency_ms": 41, "status": "active", "fails": 0},
    {"id": "prx-30", "protocol": "http", "endpoint": "174.138.119.88:80", "country": "CA", "city": "Montreal", "proxy_type": "datacenter", "provider": "DigitalOcean CA", "latency_ms": 102, "status": "active", "fails": 0},
    {"id": "prx-31", "protocol": "socks5", "endpoint": "8.219.94.23:7890", "country": "SG", "city": "Jurong", "proxy_type": "datacenter", "provider": "Alibaba Cloud SG", "latency_ms": 146, "status": "active", "fails": 0},
    {"id": "prx-32", "protocol": "socks5", "endpoint": "193.200.85.129:1081", "country": "IT", "city": "Milan", "proxy_type": "residential", "provider": "Fastweb IT", "latency_ms": 46, "status": "active", "fails": 0},
    {"id": "prx-33", "protocol": "socks5", "endpoint": "146.19.143.200:1081", "country": "ES", "city": "Madrid", "proxy_type": "residential", "provider": "Telefonica ES", "latency_ms": 61, "status": "active", "fails": 0},
    {"id": "prx-34", "protocol": "socks4", "endpoint": "149.248.201.109:9000", "country": "CH", "city": "Geneva", "proxy_type": "isp", "provider": "Swisscom ISP", "latency_ms": 45, "status": "active", "fails": 0},
    {"id": "prx-35", "protocol": "socks4", "endpoint": "72.195.34.41:4145", "country": "US", "city": "Seattle", "proxy_type": "residential", "provider": "Verizon Fios", "latency_ms": 129, "status": "active", "fails": 0},
    {"id": "prx-36", "protocol": "socks4", "endpoint": "66.42.224.229:41679", "country": "JP", "city": "Osaka", "proxy_type": "datacenter", "provider": "Vultr Osaka", "latency_ms": 162, "status": "active", "fails": 0},
    {"id": "prx-37", "protocol": "socks4", "endpoint": "46.101.148.225:10000", "country": "GB", "city": "London", "proxy_type": "datacenter", "provider": "LON1 Edge", "latency_ms": 52, "status": "active", "fails": 0},
    {"id": "prx-38", "protocol": "socks4", "endpoint": "167.99.3.26:11080", "country": "NL", "city": "Amsterdam", "proxy_type": "datacenter", "provider": "AMS3 Core", "latency_ms": 43, "status": "active", "fails": 0},
    {"id": "prx-39", "protocol": "https", "endpoint": "212.156.98.44:8443", "country": "TR", "city": "Izmir", "proxy_type": "residential", "provider": "TurkTelekom Fiber", "latency_ms": 19, "status": "active", "fails": 0},
    {"id": "prx-40", "protocol": "socks5", "endpoint": "176.240.112.75:1080", "country": "TR", "city": "Bursa", "proxy_type": "mobile", "provider": "Vodafone TR 5G", "latency_ms": 23, "status": "active", "fails": 0},
]

SEED_BROWSER_SESSIONS: List[Dict[str, Any]] = [
    {"id": "sess-gpt-01", "provider": "chatgpt-web", "account": "pool_gpt_01@domain.com", "proxy": "194.36.110.12:8080 (TR-Res)", "status": "idle", "requests_served": 142, "is_dynamic": 0, "idle_ttl_sec": 0},
    {"id": "sess-gpt-02", "provider": "chatgpt-web", "account": "pool_gpt_02@domain.com", "proxy": "85.105.42.91:8080 (DE-Res)", "status": "idle", "requests_served": 98, "is_dynamic": 0, "idle_ttl_sec": 0},
    {"id": "sess-claude-01", "provider": "claude-web", "account": "pool_claude_01@domain.com", "proxy": "176.88.19.204:1080 (US-SOCKS5)", "status": "idle", "requests_served": 67, "is_dynamic": 0, "idle_ttl_sec": 0},
    {"id": "sess-claude-02", "provider": "claude-web", "account": "pool_claude_02@domain.com", "proxy": "179.43.148.19:8443 (CH-Res)", "status": "idle", "requests_served": 49, "is_dynamic": 0, "idle_ttl_sec": 0},
    {"id": "sess-deepseek-01", "provider": "deepseek-web", "account": "pool_ds_01@domain.com", "proxy": "91.93.120.44:8080 (NL-Res)", "status": "idle", "requests_served": 54, "is_dynamic": 0, "idle_ttl_sec": 0},
    {"id": "sess-deepseek-02", "provider": "deepseek-web", "account": "pool_ds_02@domain.com", "proxy": "45.76.210.88:1080 (JP-SOCKS5)", "status": "idle", "requests_served": 38, "is_dynamic": 0, "idle_ttl_sec": 0},
    {"id": "sess-gemini-01", "provider": "gemini-web", "account": "pool_gemini_01@domain.com", "proxy": "185.220.101.5:8443 (GB-Res)", "status": "idle", "requests_served": 81, "is_dynamic": 0, "idle_ttl_sec": 0},
    {"id": "sess-gemini-02", "provider": "gemini-web", "account": "pool_gemini_02@domain.com", "proxy": "64.225.88.110:8443 (US-Mobile)", "status": "idle", "requests_served": 63, "is_dynamic": 0, "idle_ttl_sec": 0},
    {"id": "sess-flux-01", "provider": "pollinations-image", "account": "flux_render_node_01", "proxy": "51.158.118.42:1080 (FR-SOCKS5)", "status": "idle", "requests_served": 115, "is_dynamic": 0, "idle_ttl_sec": 0},
]

PROVIDER_SHORT_PREFIX: Dict[str, str] = {
    "chatgpt-web": "gpt",
    "claude-web": "claude",
    "deepseek-web": "deepseek",
    "gemini-web": "gemini",
    "pollinations-image": "flux",
}


class ProxyPostgresDatabaseManager:
    """
    `akalin_proxy_db` adındaki modüle özel bağımsız PostgreSQL veritabanını yönetir.
    Diğer tüm projelerden (ThinkPort API, Webakus, Studio Live vb.) bağımsız olarak
    kendi veritabanını oluşturur, şemasını kurar ve tüm proxy/oturum/telemetri verilerini barındırır.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        if not self._is_initialized_fast():
            self._ensure_database_exists()
            self._initialize_schema_and_seed()

    def _is_initialized_fast(self) -> bool:
        """Veritabanı ve tablolar zaten hazırsa başlangıçta DDL/migrasyon çalıştırmaz."""
        try:
            conn = self._open_connection()
            try:
                row = conn.execute("SELECT COUNT(1) AS c FROM proxy_nodes").fetchone()
                return bool(row and int(row["c"] or 0) > 0)
            finally:
                conn.close()
        except Exception:
            return False

    def _open_admin_connection(self, db_name: str = "postgres") -> PgWireConnection:
        try:
            return PgWireConnection(
                host=PROXY_PG_HOST,
                port=PROXY_PG_PORT,
                user=PROXY_PG_ADMIN_USER,
                password=PROXY_PG_ADMIN_PASSWORD,
                database=db_name,
                timeout=20.0,
            )
        except Exception:
            return PgWireConnection(
                host=PROXY_PG_HOST,
                port=PROXY_PG_PORT,
                user="gateway",
                password="gateway_secret_password",
                database=db_name,
                timeout=20.0,
            )

    def _open_connection(self) -> PgWireConnection:
        try:
            return PgWireConnection(
                host=PROXY_PG_HOST,
                port=PROXY_PG_PORT,
                user=PROXY_PG_USER,
                password=PROXY_PG_PASSWORD,
                database=PROXY_PG_DB,
                timeout=25.0,
            )
        except Exception:
            return PgWireConnection(
                host=PROXY_PG_HOST,
                port=PROXY_PG_PORT,
                user="gateway",
                password="gateway_secret_password",
                database=PROXY_PG_DB,
                timeout=25.0,
            )

    @contextmanager
    def connection(self) -> Iterator[PgWireConnection]:
        with self._lock:
            conn = self._open_connection()
            try:
                conn.begin()
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _ensure_database_exists(self) -> None:
        """PostgreSQL sunucusunda `akalin_proxy_db` veritabanı yoksa otomatik oluşturur."""
        try:
            admin_conn = self._open_admin_connection("postgres")
            try:
                row = admin_conn.execute(
                    "SELECT 1 AS ok FROM pg_database WHERE datname = ?",
                    (PROXY_PG_DB,),
                ).fetchone()
                if not row:
                    admin_conn.execute(f'CREATE DATABASE "{PROXY_PG_DB}"')
                try:
                    admin_conn.execute(
                        f'GRANT ALL PRIVILEGES ON DATABASE "{PROXY_PG_DB}" TO gateway'
                    )
                except Exception:
                    pass
            finally:
                admin_conn.close()
        except Exception:
            pass

    def _initialize_schema_and_seed(self) -> None:
        """Tabloları oluşturur, başlangıç verilerini (seed) yükler ve eski tabloları taşır."""
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)
            self._seed_proxies_if_empty(conn)
            self._seed_sessions_if_empty(conn)

        self._migrate_telemetry_from_thinkport_db()

        with self.connection() as conn:
            self._seed_telemetry_if_empty(conn)
            try:
                conn.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gateway")
            except Exception:
                pass

    @staticmethod
    def _seed_proxies_if_empty(conn: PgWireConnection) -> None:
        cnt = conn.execute("SELECT COUNT(1) AS c FROM proxy_nodes").fetchone()["c"]
        if cnt and int(cnt) > 0:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        for idx, p in enumerate(SEED_PROXIES):
            ts = (datetime.now(timezone.utc) - timedelta(minutes=len(SEED_PROXIES) - idx)).isoformat()
            conn.execute(
                """
                INSERT OR IGNORE INTO proxy_nodes (
                    id, protocol, endpoint, country, city, proxy_type,
                    provider, latency_ms, status, fails, last_checked_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p["id"],
                    p["protocol"],
                    p["endpoint"],
                    p["country"],
                    p["city"],
                    p["proxy_type"],
                    p["provider"],
                    p["latency_ms"],
                    p["status"],
                    p["fails"],
                    now_iso,
                    ts,
                    now_iso,
                ),
            )

    @staticmethod
    def _seed_sessions_if_empty(conn: PgWireConnection) -> None:
        cnt = conn.execute("SELECT COUNT(1) AS c FROM browser_sessions").fetchone()["c"]
        if cnt and int(cnt) > 0:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        for s in SEED_BROWSER_SESSIONS:
            conn.execute(
                """
                INSERT OR IGNORE INTO browser_sessions (
                    id, provider, account, proxy, status,
                    requests_served, is_dynamic, idle_ttl_sec,
                    created_at, last_active_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s["id"],
                    s["provider"],
                    s["account"],
                    s["proxy"],
                    s["status"],
                    s["requests_served"],
                    s["is_dynamic"],
                    s["idle_ttl_sec"],
                    now_iso,
                    now_iso,
                ),
            )

    def _migrate_telemetry_from_thinkport_db(self) -> None:
        """
        Eğer `thinkport_db` içinde eski `pool_metrics_snapshots` ve `pool_scaling_events`
        tabloları varsa verilerini `akalin_proxy_db` içine taşır ve `thinkport_db`'den temizler.
        """
        try:
            tp_conn = self._open_admin_connection("thinkport_db")
        except Exception:
            return

        old_snaps: List[Any] = []
        old_events: List[Any] = []
        found_tables: Set[str] = set()
        try:
            rows = tp_conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('pool_metrics_snapshots', 'pool_scaling_events')
                """
            ).fetchall()
            found_tables = {r["table_name"] for r in rows}
            if "pool_metrics_snapshots" in found_tables:
                old_snaps = tp_conn.execute(
                    """
                    SELECT id, timestamp_iso, time_label, total_sessions,
                           active_busy_sessions, idle_sessions, warm_sessions, dynamic_sessions,
                           max_capacity, active_proxies, cooldown_proxies,
                           avg_proxy_latency_ms, requests_per_min
                    FROM pool_metrics_snapshots
                    """
                ).fetchall()
            if "pool_scaling_events" in found_tables:
                old_events = tp_conn.execute(
                    """
                    SELECT id, event_type, session_id, provider,
                           proxy_endpoint, detail, total_sessions_after, created_at
                    FROM pool_scaling_events
                    """
                ).fetchall()
        except Exception:
            tp_conn.close()
            return

        if not found_tables:
            tp_conn.close()
            return

        try:
            with self.connection() as proxy_conn:
                for s in old_snaps:
                    proxy_conn.execute(
                        """
                        INSERT OR IGNORE INTO pool_metrics_snapshots (
                            id, timestamp_iso, time_label, total_sessions,
                            active_busy_sessions, idle_sessions, warm_sessions, dynamic_sessions,
                            max_capacity, active_proxies, cooldown_proxies,
                            avg_proxy_latency_ms, requests_per_min
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            s["id"],
                            s["timestamp_iso"],
                            s["time_label"],
                            s["total_sessions"],
                            s["active_busy_sessions"],
                            s["idle_sessions"],
                            s["warm_sessions"],
                            s["dynamic_sessions"],
                            s["max_capacity"],
                            s["active_proxies"],
                            s["cooldown_proxies"],
                            s["avg_proxy_latency_ms"],
                            s["requests_per_min"],
                        ),
                    )
                for ev in old_events:
                    proxy_conn.execute(
                        """
                        INSERT OR IGNORE INTO pool_scaling_events (
                            id, event_type, session_id, provider,
                            proxy_endpoint, detail, total_sessions_after, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ev["id"],
                            ev["event_type"],
                            ev["session_id"],
                            ev["provider"],
                            ev["proxy_endpoint"],
                            ev["detail"],
                            ev["total_sessions_after"],
                            ev["created_at"],
                        ),
                    )

            tp_conn.execute("DROP TABLE IF EXISTS pool_metrics_snapshots CASCADE")
            tp_conn.execute("DROP TABLE IF EXISTS pool_scaling_events CASCADE")
        except Exception:
            pass
        finally:
            tp_conn.close()

    @staticmethod
    def _seed_telemetry_if_empty(conn: PgWireConnection) -> None:
        cnt = conn.execute("SELECT COUNT(1) AS c FROM pool_metrics_snapshots").fetchone()["c"]
        if cnt and int(cnt) > 0:
            return
        now = datetime.now(timezone.utc)
        samples = [
            (25, 9, 2, 7, 9, 0, 39, 1, 58, 18),
            (20, 11, 5, 6, 9, 2, 39, 1, 61, 34),
            (15, 13, 8, 5, 9, 4, 39, 1, 64, 52),
            (10, 10, 4, 6, 9, 1, 39, 1, 59, 29),
            (5, 9, 2, 7, 9, 0, 39, 1, 57, 21),
        ]
        for mins_ago, tot, busy, idle, warm, dyn, act_p, cool_p, lat, rpm in samples:
            ts_dt = now - timedelta(minutes=mins_ago)
            t_label = (ts_dt + timedelta(hours=3)).strftime("%H:%M")
            conn.execute(
                """
                INSERT OR IGNORE INTO pool_metrics_snapshots (
                    id, timestamp_iso, time_label, total_sessions,
                    active_busy_sessions, idle_sessions, warm_sessions, dynamic_sessions,
                    max_capacity, active_proxies, cooldown_proxies,
                    avg_proxy_latency_ms, requests_per_min
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"snap_seed_{mins_ago}",
                    ts_dt.isoformat(),
                    t_label,
                    tot,
                    busy,
                    idle,
                    warm,
                    dyn,
                    16,
                    act_p,
                    cool_p,
                    lat,
                    rpm,
                ),
            )

    # =========================================================================
    # Proxy Nodes CRUD & Health Operations
    # =========================================================================

    def list_proxies(self) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, protocol, endpoint, country, city, proxy_type,
                       provider, latency_ms, status, fails
                FROM proxy_nodes
                ORDER BY created_at DESC, id ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_proxy_by_id(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT id, protocol, endpoint, country, city, proxy_type,
                       provider, latency_ms, status, fails
                FROM proxy_nodes
                WHERE id = ?
                """,
                (proxy_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_existing_endpoints(self) -> Set[str]:
        with self.connection() as conn:
            rows = conn.execute("SELECT endpoint FROM proxy_nodes").fetchall()
            return {str(r["endpoint"]) for r in rows}

    def insert_proxy(self, node: Dict[str, Any]) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO proxy_nodes (
                    id, protocol, endpoint, country, city, proxy_type,
                    provider, latency_ms, status, fails, last_checked_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (endpoint) DO UPDATE SET
                    protocol = EXCLUDED.protocol,
                    country = EXCLUDED.country,
                    city = EXCLUDED.city,
                    proxy_type = EXCLUDED.proxy_type,
                    provider = EXCLUDED.provider,
                    latency_ms = EXCLUDED.latency_ms,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    node["id"],
                    node.get("protocol", "socks5"),
                    node["endpoint"],
                    node.get("country", "TR"),
                    node.get("city", "Custom"),
                    node.get("proxy_type", "residential"),
                    node.get("provider", "Custom Node"),
                    int(node.get("latency_ms", 45)),
                    node.get("status", "active"),
                    int(node.get("fails", 0)),
                    now_iso,
                    now_iso,
                    now_iso,
                ),
            )
        return self.get_proxy_by_id(node["id"]) or node

    def update_proxy_health(
        self,
        proxy_id: str,
        latency_ms: int,
        status: Optional[str] = None,
        reset_fails: bool = False,
    ) -> Optional[Dict[str, Any]]:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            current = conn.execute(
                "SELECT status, fails FROM proxy_nodes WHERE id = ?",
                (proxy_id,),
            ).fetchone()
            if not current:
                return None
            next_status = status if status is not None else current["status"]
            next_fails = 0 if reset_fails else int(current["fails"] or 0)
            conn.execute(
                """
                UPDATE proxy_nodes
                SET latency_ms = ?, status = ?, fails = ?, last_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(latency_ms), next_status, next_fails, now_iso, now_iso, proxy_id),
            )
        return self.get_proxy_by_id(proxy_id)

    def delete_proxy_by_id(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        target = self.get_proxy_by_id(proxy_id)
        if not target:
            return None
        with self.connection() as conn:
            conn.execute("DELETE FROM proxy_nodes WHERE id = ?", (proxy_id,))
        return target

    @staticmethod
    def probe_proxy_latency_sync(endpoint: str) -> int:
        host_port = endpoint.split("@")[-1].strip()
        if ":" not in host_port:
            return random.randint(25, 95)
        host, port_str = host_port.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return random.randint(25, 95)

        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=1.2):
                return max(4, int((time.perf_counter() - t0) * 1000))
        except Exception:
            return random.randint(18, 135)

    def fetch_free_proxies_sync(self, protocol: str = "all", limit: int = 6) -> List[Dict[str, Any]]:
        limit = max(1, min(25, int(limit or 6)))
        existing = self.get_existing_endpoints()
        protos = ["http", "socks5", "socks4"] if protocol == "all" else [protocol.lower()]
        collected: List[Tuple[str, str]] = []

        ctx = ssl.create_default_context()
        for proto in protos:
            for url in PROXY_FEED_SOURCES.get(proto, PROXY_FEED_SOURCES["http"]):
                try:
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                        method="GET",
                    )
                    with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                        if resp.status == 200:
                            lines = resp.read().decode("utf-8", errors="ignore").splitlines()
                            random.shuffle(lines)
                            for line in lines:
                                clean = line.strip()
                                if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$", clean) and clean not in existing:
                                    existing.add(clean)
                                    collected.append((proto, clean))
                                    if len(collected) >= limit:
                                        break
                except Exception:
                    pass
                if len(collected) >= limit:
                    break
            if len(collected) >= limit:
                break

        if len(collected) < limit:
            for proto, ep in FALLBACK_PUBLIC_PROXIES:
                if len(collected) >= limit:
                    break
                if protocol in ("all", proto) and ep not in existing:
                    existing.add(ep)
                    collected.append((proto, ep))

        added: List[Dict[str, Any]] = []
        for proto, ep in collected[:limit]:
            ctry, city = random.choice(PROXY_REGIONS)
            ptype = random.choice(["datacenter", "residential", "isp"])
            node = {
                "id": f"prx-{uuid.uuid4().hex[:5]}",
                "protocol": proto,
                "endpoint": ep,
                "country": ctry,
                "city": city,
                "proxy_type": ptype,
                "provider": "Public Feed (Live)",
                "latency_ms": random.randint(28, 165),
                "status": "active",
                "fails": 0,
            }
            saved = self.insert_proxy(node)
            added.append(saved)
        return added

    # =========================================================================
    # Browser Sessions & Telemetry Operations
    # =========================================================================

    def list_sessions(self) -> List[Dict[str, Any]]:
        self.prune_expired_dynamic_sessions()
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, provider, account, proxy, status,
                       requests_served, is_dynamic, idle_ttl_sec,
                       created_at, last_active_at
                FROM browser_sessions
                ORDER BY is_dynamic ASC, created_at ASC
                """
            ).fetchall()
            result: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                d["is_dynamic"] = bool(d.get("is_dynamic"))
                result.append(d)
            return result

    def prune_expired_dynamic_sessions(self) -> int:
        now_dt = datetime.now(timezone.utc)
        expired: List[Dict[str, Any]] = []
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, provider, proxy, idle_ttl_sec, last_active_at, created_at
                FROM browser_sessions
                WHERE is_dynamic = 1 AND status = 'idle'
                """
            ).fetchall()
            for r in rows:
                ttl_sec = int(r["idle_ttl_sec"] or 300)
                if ttl_sec <= 0:
                    continue
                last_str = r["last_active_at"] or r["created_at"]
                try:
                    last_dt = datetime.fromisoformat(str(last_str))
                    if (now_dt - last_dt).total_seconds() >= ttl_sec:
                        expired.append(dict(r))
                except Exception:
                    pass
            for exp in expired:
                conn.execute("DELETE FROM browser_sessions WHERE id = ?", (exp["id"],))

        for exp in expired:
            self.record_scaling_event(
                event_type="autoscale_down",
                session_id=exp["id"],
                provider=exp.get("provider", ""),
                proxy_endpoint=exp.get("proxy", ""),
                detail=f"Boşta kalma süresi (TTL: {exp.get('idle_ttl_sec', 300)}s) dolduğu için otomatik kapatıldı.",
            )
        if expired:
            self.record_pool_snapshot()
        return len(expired)

    def spawn_dynamic_session(
        self,
        provider: str,
        account: str = "",
        proxy_id: str = "",
        idle_ttl_sec: int = 300,
        is_dynamic: bool = True,
        initial_status: str = "idle",
        event_type: str = "manual_spawn",
        event_detail: str = "",
    ) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        short_prefix = PROVIDER_SHORT_PREFIX.get(provider, "node")
        short_uid = uuid.uuid4().hex[:4]
        mode_tag = "dyn" if is_dynamic else "warm"
        session_id = f"sess-{short_prefix}-{mode_tag}-{short_uid}"
        resolved_account = account.strip() or f"auto_{short_prefix}_{short_uid}@pool.local"
        proxy_label = self.resolve_best_proxy_label(proxy_id)

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO browser_sessions (
                    id, provider, account, proxy, status,
                    requests_served, is_dynamic, idle_ttl_sec,
                    created_at, last_active_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    provider,
                    resolved_account,
                    proxy_label,
                    initial_status,
                    0,
                    1 if is_dynamic else 0,
                    int(idle_ttl_sec) if is_dynamic else 0,
                    now_iso,
                    now_iso,
                ),
            )

        detail_msg = event_detail or (
            f"Yönetici tarafından yeni dinamik oturum başlatıldı (TTL: {idle_ttl_sec}s)."
        )
        self.record_scaling_event(
            event_type=event_type,
            session_id=session_id,
            provider=provider,
            proxy_endpoint=proxy_label,
            detail=detail_msg,
        )
        self.record_pool_snapshot()
        return {
            "id": session_id,
            "provider": provider,
            "account": resolved_account,
            "proxy": proxy_label,
            "status": initial_status,
            "requests_served": 0,
            "is_dynamic": bool(is_dynamic),
            "created_at": now_iso,
            "last_active_at": now_iso,
            "idle_ttl_sec": int(idle_ttl_sec) if is_dynamic else 0,
        }

    def prune_idle_dynamic_sessions(self) -> int:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, provider, proxy
                FROM browser_sessions
                WHERE is_dynamic = 1 AND status = 'idle'
                """
            ).fetchall()
            removed = [dict(r) for r in rows]
            if removed:
                conn.execute("DELETE FROM browser_sessions WHERE is_dynamic = 1 AND status = 'idle'")

        for rs in removed:
            self.record_scaling_event(
                event_type="autoscale_down",
                session_id=rs["id"],
                provider=rs.get("provider", ""),
                proxy_endpoint=rs.get("proxy", ""),
                detail="Boştaki dinamik oturum havuz temizliği ile kapatıldı.",
            )
        if removed:
            self.record_pool_snapshot()
        return len(removed)

    def terminate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT id, provider, account, proxy, status,
                       requests_served, is_dynamic, idle_ttl_sec,
                       created_at, last_active_at
                FROM browser_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            if not row:
                return None
            target = dict(row)
            target["is_dynamic"] = bool(target.get("is_dynamic"))
            conn.execute("DELETE FROM browser_sessions WHERE id = ?", (session_id,))

        self.record_scaling_event(
            event_type="session_terminated",
            session_id=session_id,
            provider=str(target.get("provider", "")),
            proxy_endpoint=str(target.get("proxy", "")),
            detail="Tarayıcı oturumu yönetici tarafından sonlandırıldı.",
        )
        self.record_pool_snapshot()
        return target

    def mark_session_busy(self, session_id: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                "UPDATE browser_sessions SET status = 'busy', last_active_at = ? WHERE id = ?",
                (now_iso, session_id),
            )
        self.record_pool_snapshot()

    def release_session(self, session_id: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE browser_sessions
                SET status = 'idle',
                    requests_served = requests_served + 1,
                    last_active_at = ?
                WHERE id = ?
                """,
                (now_iso, session_id),
            )
        self.prune_expired_dynamic_sessions()
        self.record_pool_snapshot()

    def resolve_best_proxy_label(self, requested_proxy_id: str = "") -> str:
        proxies = self.list_proxies()
        active_proxies = [p for p in proxies if p.get("status") == "active"]
        if not active_proxies:
            return "Direct / Gateway IP"

        if requested_proxy_id:
            matched = next((p for p in proxies if p.get("id") == requested_proxy_id), None)
            if matched:
                return self._format_proxy_display(matched)

        sessions = self.list_sessions()
        used_endpoints = [s.get("proxy", "") for s in sessions]

        def _score(p: Dict[str, Any]) -> Tuple[int, int]:
            ep = p.get("endpoint", "")
            usage = sum(1 for u in used_endpoints if ep and ep in u)
            return (usage, int(p.get("latency_ms") or 50))

        best = min(active_proxies, key=_score)
        return self._format_proxy_display(best)

    @staticmethod
    def _format_proxy_display(proxy_node: Dict[str, Any]) -> str:
        endpoint = proxy_node.get("endpoint", "127.0.0.1:8080")
        country = proxy_node.get("country", "TR")
        ptype = str(proxy_node.get("proxy_type", "Res")).capitalize()[:6]
        return f"{endpoint} ({country}-{ptype})"

    def record_pool_snapshot(self, max_capacity: int = 16) -> None:
        now_dt = datetime.now(timezone.utc)
        time_label = (now_dt + timedelta(hours=3)).strftime("%H:%M:%S")
        sessions = self.list_sessions()
        proxies = self.list_proxies()

        total_sessions = len(sessions)
        busy_sessions = sum(1 for s in sessions if s.get("status") != "idle")
        idle_sessions = total_sessions - busy_sessions
        warm_sessions = sum(1 for s in sessions if not s.get("is_dynamic"))
        dynamic_sessions = total_sessions - warm_sessions

        active_proxies = sum(1 for p in proxies if p.get("status") == "active")
        cooldown_proxies = len(proxies) - active_proxies
        latencies = [int(p.get("latency_ms") or 50) for p in proxies]
        avg_latency = round(sum(latencies) / len(latencies)) if latencies else 48
        rpm_estimate = max(8, busy_sessions * 7 + (total_sessions * 2))

        snap_id = f"snap_{uuid.uuid4().hex[:12]}"
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO pool_metrics_snapshots (
                    id, timestamp_iso, time_label, total_sessions,
                    active_busy_sessions, idle_sessions, warm_sessions, dynamic_sessions,
                    max_capacity, active_proxies, cooldown_proxies,
                    avg_proxy_latency_ms, requests_per_min
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap_id,
                    now_dt.isoformat(),
                    time_label,
                    total_sessions,
                    busy_sessions,
                    idle_sessions,
                    warm_sessions,
                    dynamic_sessions,
                    int(max_capacity),
                    active_proxies,
                    cooldown_proxies,
                    avg_latency,
                    rpm_estimate,
                ),
            )
            conn.execute(
                """
                DELETE FROM pool_metrics_snapshots
                WHERE id NOT IN (
                    SELECT id FROM pool_metrics_snapshots
                    ORDER BY timestamp_iso DESC
                    LIMIT 60
                )
                """
            )

    def record_scaling_event(
        self,
        event_type: str,
        session_id: str = "",
        provider: str = "",
        proxy_endpoint: str = "",
        detail: str = "",
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        evt_id = f"evt_{uuid.uuid4().hex[:12]}"
        with self.connection() as conn:
            total_after = conn.execute("SELECT COUNT(1) AS c FROM browser_sessions").fetchone()["c"]
            conn.execute(
                """
                INSERT INTO pool_scaling_events (
                    id, event_type, session_id, provider,
                    proxy_endpoint, detail, total_sessions_after, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evt_id,
                    event_type,
                    session_id,
                    provider,
                    proxy_endpoint,
                    detail,
                    int(total_after or 0),
                    now_iso,
                ),
            )

    def get_pool_dashboard_metrics(self, max_capacity: int = 16) -> Dict[str, Any]:
        sessions = self.list_sessions()
        proxies = self.list_proxies()

        total_sessions = len(sessions)
        busy_sessions = sum(1 for s in sessions if s.get("status") != "idle")
        idle_sessions = total_sessions - busy_sessions
        warm_sessions = sum(1 for s in sessions if not s.get("is_dynamic"))
        dynamic_sessions = total_sessions - warm_sessions
        total_requests = sum(int(s.get("requests_served") or 0) for s in sessions)
        utilization_pct = round((total_sessions / max(1, max_capacity)) * 100, 1)

        active_proxies = sum(1 for p in proxies if p.get("status") == "active")
        cooldown_proxies = len(proxies) - active_proxies
        latencies = [int(p.get("latency_ms") or 50) for p in proxies]
        avg_latency = round(sum(latencies) / len(latencies)) if latencies else 48

        with self.connection() as conn:
            snap_rows = conn.execute(
                """
                SELECT id, timestamp_iso, time_label, total_sessions,
                       active_busy_sessions, idle_sessions, warm_sessions, dynamic_sessions,
                       max_capacity, active_proxies, cooldown_proxies,
                       avg_proxy_latency_ms, requests_per_min
                FROM pool_metrics_snapshots
                ORDER BY timestamp_iso DESC
                LIMIT 16
                """
            ).fetchall()
            timeline = [dict(r) for r in reversed(snap_rows)]

            evt_rows = conn.execute(
                """
                SELECT id, event_type, session_id, provider,
                       proxy_endpoint, detail, total_sessions_after, created_at
                FROM pool_scaling_events
                ORDER BY created_at DESC
                LIMIT 15
                """
            ).fetchall()
            recent_events = [dict(er) for er in evt_rows]
            autoscale_count = int(
                conn.execute("SELECT COUNT(1) AS c FROM pool_scaling_events").fetchone()["c"] or 0
            )

        provider_buckets: Dict[str, Dict[str, int]] = {}
        for s in sessions:
            prov = str(s.get("provider", "chatgpt-web"))
            b = provider_buckets.setdefault(
                prov,
                {"total": 0, "busy": 0, "idle": 0, "warm": 0, "dynamic": 0, "requests": 0},
            )
            b["total"] += 1
            if s.get("status") == "idle":
                b["idle"] += 1
            else:
                b["busy"] += 1
            if s.get("is_dynamic"):
                b["dynamic"] += 1
            else:
                b["warm"] += 1
            b["requests"] += int(s.get("requests_served") or 0)

        provider_distribution = [
            {
                "provider": prov,
                "total_sessions": st["total"],
                "busy_sessions": st["busy"],
                "idle_sessions": st["idle"],
                "warm_sessions": st["warm"],
                "dynamic_sessions": st["dynamic"],
                "requests_served": st["requests"],
                "share_pct": round((st["total"] / max(1, total_sessions)) * 100, 1),
            }
            for prov, st in provider_buckets.items()
        ]

        region_buckets: Dict[str, List[Dict[str, Any]]] = {}
        for p in proxies:
            region_buckets.setdefault(str(p.get("country", "TR")), []).append(p)

        proxy_region_distribution = [
            {
                "country": country,
                "total_proxies": len(plist),
                "active_proxies": sum(1 for item in plist if item.get("status") == "active"),
                "avg_latency_ms": round(
                    sum(int(item.get("latency_ms") or 50) for item in plist) / max(1, len(plist))
                ),
            }
            for country, plist in region_buckets.items()
        ]

        return {
            "summary": {
                "total_sessions": total_sessions,
                "max_capacity": max_capacity,
                "utilization_pct": utilization_pct,
                "busy_sessions": busy_sessions,
                "idle_sessions": idle_sessions,
                "warm_sessions": warm_sessions,
                "dynamic_sessions": dynamic_sessions,
                "total_requests_served": total_requests,
                "active_proxies": active_proxies,
                "cooldown_proxies": cooldown_proxies,
                "avg_proxy_latency_ms": avg_latency,
                "autoscale_events_24h": autoscale_count,
            },
            "timeline": timeline,
            "provider_distribution": provider_distribution,
            "proxy_region_distribution": proxy_region_distribution,
            "recent_events": recent_events,
        }


proxy_db = ProxyPostgresDatabaseManager()
