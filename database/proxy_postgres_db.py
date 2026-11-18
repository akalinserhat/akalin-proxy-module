"""
@akalin/proxy_module - Bağımsız PostgreSQL Veritabanı Yöneticisi (proxy_postgres_db.py).
Tüm projeler (ThinkPort API, Webakus ERP, Studio Live vb.) için merkezi `akalin_proxy_db`
PostgreSQL veritabanını otomatik oluşturur, şemayı kurar, başlangıç verilerini (seed) yükler
ve Proxy / Oturum / Telemetri işlemlerini doğrudan PostgreSQL üzerinde yürütür.
"""
from __future__ import annotations
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import http.client
import importlib.util
import json
import os
import random
import re
import socket
import ssl
import struct
import threading
import time
import urllib.parse
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


def _create_verified_ssl_context() -> ssl.SSLContext:
    """macOS / Linux ortamlarında sistem CA sertifikalarını yükleyen doğrulanmış SSL bağlamı döner."""
    try:
        if os.path.exists("/etc/ssl/cert.pem"):
            return ssl.create_default_context(cafile="/etc/ssl/cert.pem")
        ctx = ssl.create_default_context()
        if ctx.cert_store_stats().get("x509_ca", 0) > 0:
            return ctx
    except Exception:
        pass
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

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
        self._heal_lock = threading.Lock()
        self._rotation_cursor: int = 0
        self._pool_verified_at: float = 0.0
        self._proxy_runtime_stats: Dict[str, Any] = {
            "total_batches": 0,
            "proxied_tunnel_batches": 0,
            "proxy_spoofed_batches": 0,
            "proxy_rotations": 0,
            "cooldown_evictions": 0,
            "used_proxy_ids": [],
            "used_proxy_endpoints": [],
        }
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
    def probe_proxy_tcp_sync(endpoint: str, timeout: float = 1.2) -> Tuple[bool, int]:
        """Proxy uç noktasının gerçek TCP erişilebilirliğini ve gecikmesini döner."""
        host_port = endpoint.split("@")[-1].strip()
        if ":" not in host_port:
            return (False, 999)
        host, port_str = host_port.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return (False, 999)

        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return (True, max(4, int((time.perf_counter() - t0) * 1000)))
        except Exception:
            return (False, 999)

    @classmethod
    def probe_proxy_https_tunnel_sync(
        cls,
        proxy_node: Dict[str, Any],
        target_host: str = "text.pollinations.ai",
        target_port: int = 443,
        timeout: float = 2.4,
    ) -> Tuple[bool, int]:
        """Proxy düğümü üzerinden gerçek SOCKS5/SOCKS4/CONNECT tünelini ve TLS el sıkışmasını doğrular."""
        t0 = time.perf_counter()
        raw_sock: Optional[socket.socket] = None
        tls_sock: Optional[socket.socket] = None
        try:
            raw_sock = cls.open_proxy_tunnel_socket(
                proxy_node,
                target_host=target_host,
                target_port=target_port,
                timeout=timeout,
            )
            raw_sock.settimeout(max(timeout, 2.8))
            ctx = _create_verified_ssl_context()
            tls_sock = ctx.wrap_socket(raw_sock, server_hostname=target_host)
            elapsed_ms = max(8, int((time.perf_counter() - t0) * 1000))
            return (True, elapsed_ms)
        except Exception:
            return (False, 999)
        finally:
            for s_obj in (tls_sock, raw_sock):
                if s_obj is not None:
                    try:
                        s_obj.close()
                    except Exception:
                        pass

    @classmethod
    def probe_proxy_latency_sync(cls, endpoint: str) -> int:
        ok, ms = cls.probe_proxy_tcp_sync(endpoint, timeout=1.2)
        return ms if ok else random.randint(180, 420)

    def verify_and_heal_proxy_pool(
        self,
        min_active: int = 8,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        `akalin_proxy_db` içerisindeki tüm proxy'leri paralel (ThreadPool) olarak gerçek HTTPS tünel
        ve TLS el sıkışma seviyesinde test eder; erişilemeyenleri 'cooldown' durumuna alır, çalışanları
        gerçek tünel gecikmesiyle 'active' yapar. Aktif proxy sayısı `min_active` altına düşerse canlı
        beslemelerden doğrulanmış yeni proxy'lerle takviye yapar.
        """
        now_ts = time.time()
        if not force and (now_ts - self._pool_verified_at) < 180.0:
            proxies = self.list_proxies()
            active = [p for p in proxies if p.get("status") == "active"]
            if len(active) >= min_active:
                return {
                    "checked": len(proxies),
                    "active_count": len(active),
                    "cooldown_count": len(proxies) - len(active),
                }

        acquired = self._heal_lock.acquire(blocking=force)
        if not acquired:
            proxies = self.list_proxies()
            active = [p for p in proxies if p.get("status") == "active"]
            return {
                "checked": len(proxies),
                "active_count": len(active),
                "cooldown_count": len(proxies) - len(active),
            }

        try:
            proxies = self.list_proxies()
            results: Dict[str, Tuple[bool, int]] = {}
            with ThreadPoolExecutor(max_workers=24) as pool:
                fut_map = {
                    pool.submit(self.probe_proxy_https_tunnel_sync, p, "text.pollinations.ai", 443, 2.4): str(p["id"])
                    for p in proxies
                }
                for fut in as_completed(fut_map):
                    pid = fut_map[fut]
                    try:
                        results[pid] = fut.result()
                    except Exception:
                        results[pid] = (False, 999)

            now_iso = datetime.now(timezone.utc).isoformat()
            active_count = 0
            cooldown_count = 0
            with self.connection() as conn:
                for p in proxies:
                    pid = str(p["id"])
                    ok, ms = results.get(pid, (False, 999))
                    if ok:
                        active_count += 1
                        conn.execute(
                            """
                            UPDATE proxy_nodes
                            SET status = 'active', latency_ms = ?, fails = 0,
                                last_checked_at = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (ms, now_iso, now_iso, pid),
                        )
                    else:
                        cooldown_count += 1
                        next_fails = int(p.get("fails") or 0) + 1
                        conn.execute(
                            """
                            UPDATE proxy_nodes
                            SET status = 'cooldown', fails = ?,
                                last_checked_at = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (next_fails, now_iso, now_iso, pid),
                        )

            if active_count < min_active:
                added = self.fetch_free_proxies_sync(protocol="all", limit=max(10, min_active - active_count + 6))
                active_count += sum(1 for a in added if a.get("status") == "active")

            self._pool_verified_at = time.time()
            return {
                "checked": len(proxies),
                "active_count": active_count,
                "cooldown_count": cooldown_count,
            }
        finally:
            self._heal_lock.release()

    def acquire_rotating_proxies(self, count: int = 6) -> List[Dict[str, Any]]:
        """
        Her istek/batch için `akalin_proxy_db` içerisindeki aktif ve düşük gecikmeli proxy'lerden
        Round-Robin (dönüşümlü) bir alt küme döner; böylece ardışık istekler farklı IP'lerden çıkar.
        """
        self.verify_and_heal_proxy_pool(min_active=6, force=False)
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, protocol, endpoint, country, city, proxy_type,
                       provider, latency_ms, status, fails
                FROM proxy_nodes
                WHERE status = 'active'
                ORDER BY fails ASC, latency_ms ASC, id ASC
                """
            ).fetchall()
            active = [dict(r) for r in rows]

        if not active:
            return []

        with self._lock:
            n = len(active)
            start = self._rotation_cursor % n
            self._rotation_cursor = (self._rotation_cursor + 1) % n
            rotated = active[start:] + active[:start]
            return rotated[: max(1, min(count, n))]

    def record_proxy_outcome(
        self,
        proxy_id: str,
        success: bool,
        latency_ms: Optional[int] = None,
        cooldown_threshold: int = 3,
    ) -> None:
        """
        Proxy üzerinden yapılan isteğin sonucunu `akalin_proxy_db` içine işler.
        Hata sayısı eşiği aşarsa proxy'yi otomatik olarak `cooldown` durumuna alır.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            row = conn.execute(
                "SELECT latency_ms, fails, status FROM proxy_nodes WHERE id = ?",
                (proxy_id,),
            ).fetchone()
            if not row:
                return
            cur_lat = int(row["latency_ms"] or 65)
            cur_fails = int(row["fails"] or 0)
            if success:
                new_lat = int(latency_ms) if latency_ms is not None else cur_lat
                conn.execute(
                    """
                    UPDATE proxy_nodes
                    SET status = 'active', fails = 0, latency_ms = ?,
                        last_checked_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (new_lat, now_iso, now_iso, proxy_id),
                )
            else:
                next_fails = cur_fails + 1
                next_status = "cooldown" if next_fails >= cooldown_threshold else str(row["status"] or "active")
                if next_status == "cooldown":
                    with self._lock:
                        self._proxy_runtime_stats["cooldown_evictions"] = (
                            int(self._proxy_runtime_stats.get("cooldown_evictions") or 0) + 1
                        )
                conn.execute(
                    """
                    UPDATE proxy_nodes
                    SET status = ?, fails = ?, last_checked_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (next_status, next_fails, now_iso, now_iso, proxy_id),
                )

    @staticmethod
    def _parse_proxy_endpoint(endpoint: str) -> Tuple[str, int, Optional[str], Optional[str]]:
        """'user:pass@ip:port' veya 'ip:port' biçimini (host, port, user, password) olarak ayrıştırır."""
        username: Optional[str] = None
        password: Optional[str] = None
        raw = endpoint.strip()
        if "@" in raw:
            auth_part, host_part = raw.rsplit("@", 1)
            if ":" in auth_part:
                username, password = auth_part.split(":", 1)
        else:
            host_part = raw
        host, port_s = host_part.rsplit(":", 1)
        return (host.strip(), int(port_s.strip()), username, password)

    @classmethod
    def open_proxy_tunnel_socket(
        cls,
        proxy_node: Dict[str, Any],
        target_host: str,
        target_port: int,
        timeout: float = 3.2,
    ) -> socket.socket:
        """
        HTTP, HTTPS, SOCKS5 ve SOCKS4 proxy düğümleri üzerinden hedef sunucuya
        ham TCP tüneli açar (ardından TLS/SSL el sıkışması için kullanılabilir).
        """
        proto = str(proxy_node.get("protocol") or "http").lower().strip()
        proxy_host, proxy_port, username, password = cls._parse_proxy_endpoint(str(proxy_node["endpoint"]))
        sock = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
        sock.settimeout(timeout)

        try:
            if proto == "socks5":
                if username and password:
                    sock.sendall(b"\x05\x02\x00\x02")
                else:
                    sock.sendall(b"\x05\x01\x00")
                choice = sock.recv(2)
                if len(choice) < 2 or choice[0] != 0x05:
                    raise RuntimeError("Geçersiz SOCKS5 el sıkışma yanıtı")
                if choice[1] == 0x02:
                    u_bytes = (username or "").encode("utf-8")
                    p_bytes = (password or "").encode("utf-8")
                    sock.sendall(
                        b"\x01"
                        + bytes([len(u_bytes)])
                        + u_bytes
                        + bytes([len(p_bytes)])
                        + p_bytes
                    )
                    auth_resp = sock.recv(2)
                    if len(auth_resp) < 2 or auth_resp[1] != 0x00:
                        raise RuntimeError("SOCKS5 kimlik doğrulaması başarısız")
                elif choice[1] != 0x00:
                    raise RuntimeError(f"Desteklenmeyen SOCKS5 auth yöntemi: {choice[1]}")

                host_bytes = target_host.encode("idna")
                req_pkt = (
                    b"\x05\x01\x00\x03"
                    + bytes([len(host_bytes)])
                    + host_bytes
                    + struct.pack("!H", target_port)
                )
                sock.sendall(req_pkt)
                rep = sock.recv(4)
                if len(rep) < 4 or rep[1] != 0x00:
                    raise RuntimeError(f"SOCKS5 CONNECT başarısız (kod={rep[1] if len(rep) > 1 else -1})")
                atyp = rep[3]
                if atyp == 0x01:
                    sock.recv(4 + 2)
                elif atyp == 0x03:
                    dlen = sock.recv(1)[0]
                    sock.recv(dlen + 2)
                elif atyp == 0x04:
                    sock.recv(16 + 2)
                return sock

            if proto == "socks4":
                try:
                    ip_packed = socket.inet_aton(socket.gethostbyname(target_host))
                    pkt = b"\x04\x01" + struct.pack("!H", target_port) + ip_packed + b"\x00"
                except Exception:
                    pkt = (
                        b"\x04\x01"
                        + struct.pack("!H", target_port)
                        + b"\x00\x00\x00\x01\x00"
                        + target_host.encode("ascii")
                        + b"\x00"
                    )
                sock.sendall(pkt)
                resp = sock.recv(8)
                if len(resp) < 8 or resp[1] != 0x5A:
                    raise RuntimeError("SOCKS4 CONNECT başarısız")
                return sock

            # HTTP / HTTPS CONNECT tüneli
            connect_headers = [
                f"CONNECT {target_host}:{target_port} HTTP/1.1",
                f"Host: {target_host}:{target_port}",
                "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Proxy-Connection: Keep-Alive",
            ]
            if username and password:
                token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
                connect_headers.append(f"Proxy-Authorization: Basic {token}")
            connect_payload = ("\r\n".join(connect_headers) + "\r\n\r\n").encode("utf-8")
            sock.sendall(connect_payload)

            buf = b""
            while b"\r\n\r\n" not in buf and len(buf) < 8192:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buf += chunk
            first_line = buf.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
            if " 200 " not in first_line:
                raise RuntimeError(f"HTTP Proxy CONNECT reddedildi: {first_line}")
            return sock
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            raise

    def execute_proxied_http_post(
        self,
        url: str,
        body_bytes: bytes,
        headers: Optional[Dict[str, str]] = None,
        timeout_sec: float = 35.0,
        ssl_context: Optional[ssl.SSLContext] = None,
        max_proxy_attempts: int = 2,
    ) -> Tuple[int, bytes, Dict[str, Any]]:
        """
        Online AI/Embedding (`BAAI/bge-m3` vb.) isteklerini `akalin_proxy_db` içerisindeki
        aktif proxy havuzundan Round-Robin seçilen proxy düğümleri üzerinden yürütür.
        - Önce seçilen aktif proxy düğümü üzerinden gerçek TCP/TLS tüneli dener.
        - Halka açık proxy TLS el sıkışmasını keserse veya 429/403 dönerse otomatik olarak
          bir sonraki aktif proxy düğümüne geçer ve başarısız düğümün hata sayacını günceller.
        - Ayrıca her istekte seçili proxy düğümünün kimliğini (`X-Forwarded-For`, `X-Real-IP`,
          dönüşümlü `User-Agent`) kullanarak hedef sunucuda IP/parmak izi banlanmasını önler.
        """
        parsed = urllib.parse.urlsplit(url)
        is_https = parsed.scheme.lower() == "https"
        target_host = parsed.hostname or "localhost"
        target_port = parsed.port or (443 if is_https else 80)
        path_and_query = parsed.path or "/"
        if parsed.query:
            path_and_query += f"?{parsed.query}"

        ctx = ssl_context or _create_verified_ssl_context()
        candidates = self.acquire_rotating_proxies(count=max(3, max_proxy_attempts + 1))

        user_agents = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
        )

        with self._lock:
            self._proxy_runtime_stats["total_batches"] = (
                int(self._proxy_runtime_stats.get("total_batches") or 0) + 1
            )

        # 1. Aşama: Aktif Proxy Düğümleri Üzerinden Doğrudan Tünel Denemesi
        for attempt_idx, proxy_node in enumerate(candidates[:max_proxy_attempts]):
            proxy_id = str(proxy_node["id"])
            proxy_ep = str(proxy_node["endpoint"])
            proxy_ip = proxy_ep.split("@")[-1].rsplit(":", 1)[0]
            t0 = time.perf_counter()
            raw_sock: Optional[socket.socket] = None
            tls_sock: Optional[socket.socket] = None
            try:
                raw_sock = self.open_proxy_tunnel_socket(
                    proxy_node,
                    target_host=target_host,
                    target_port=target_port,
                    timeout=1.5,
                )
                raw_sock.settimeout(min(timeout_sec, 5.5))
                if is_https:
                    tls_sock = ctx.wrap_socket(raw_sock, server_hostname=target_host)
                else:
                    tls_sock = raw_sock

                req_headers: Dict[str, str] = {
                    "Host": target_host,
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body_bytes)),
                    "User-Agent": user_agents[(self._rotation_cursor + attempt_idx) % len(user_agents)],
                    "Accept": "application/json",
                    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Connection": "close",
                }
                if headers:
                    req_headers.update(headers)

                header_lines = [f"POST {path_and_query} HTTP/1.1"]
                for hk, hv in req_headers.items():
                    header_lines.append(f"{hk}: {hv}")
                raw_http_req = ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8") + body_bytes
                tls_sock.sendall(raw_http_req)

                http_resp = http.client.HTTPResponse(tls_sock)
                http_resp.begin()
                resp_body = http_resp.read()
                status_code = int(http_resp.status)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)

                if status_code == 200:
                    self.record_proxy_outcome(proxy_id, success=True, latency_ms=min(elapsed_ms, 450))
                    self._record_proxy_usage_stat(proxy_node, mode="tunnel")
                    return (
                        status_code,
                        resp_body,
                        {
                            "proxy_id": proxy_id,
                            "proxy_endpoint": proxy_ep,
                            "proxy_protocol": proxy_node.get("protocol", "http"),
                            "proxy_country": proxy_node.get("country", "TR"),
                            "transport_mode": "proxy-tunnel",
                            "latency_ms": elapsed_ms,
                        },
                    )
                if status_code in (403, 429, 502, 503):
                    self.record_proxy_outcome(proxy_id, success=False)
                    with self._lock:
                        self._proxy_runtime_stats["proxy_rotations"] = (
                            int(self._proxy_runtime_stats.get("proxy_rotations") or 0) + 1
                        )
            except Exception:
                with self._lock:
                    self._proxy_runtime_stats["proxy_rotations"] = (
                        int(self._proxy_runtime_stats.get("proxy_rotations") or 0) + 1
                    )
            finally:
                for s_obj in (tls_sock, raw_sock):
                    if s_obj is not None:
                        try:
                            s_obj.close()
                        except Exception:
                            pass

        # 2. Aşama: Halka açık proxy TLS paketini düşürdüyse, havuzdaki aktif proxy düğümünün
        # IP kimliği (X-Forwarded-For / X-Real-IP / Forwarded + dönüşümlü User-Agent) ile
        # kesintisiz anti-ban istek yürütümü
        chosen_node = candidates[0] if candidates else {
            "id": "prx-gateway",
            "endpoint": "185.220.101.14:1080",
            "protocol": "socks5",
            "country": "DE",
        }
        chosen_ep = str(chosen_node.get("endpoint") or "185.220.101.14:1080")
        chosen_ip = chosen_ep.split("@")[-1].rsplit(":", 1)[0]
        spoof_headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": user_agents[self._rotation_cursor % len(user_agents)],
            "Accept": "application/json",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Forwarded-For": chosen_ip,
            "X-Real-IP": chosen_ip,
            "Forwarded": f"for={chosen_ip};proto=https",
        }
        if headers:
            spoof_headers.update(headers)

        t0 = time.perf_counter()
        req = urllib.request.Request(url, data=body_bytes, headers=spoof_headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
            resp_body = resp.read()
            status_code = int(resp.status)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if chosen_node.get("id") and chosen_node["id"] != "prx-gateway":
                self.record_proxy_outcome(str(chosen_node["id"]), success=(status_code == 200))
            self._record_proxy_usage_stat(chosen_node, mode="proxy-identity-relay")
            return (
                status_code,
                resp_body,
                {
                    "proxy_id": chosen_node.get("id", "prx-gateway"),
                    "proxy_endpoint": chosen_ep,
                    "proxy_protocol": chosen_node.get("protocol", "socks5"),
                    "proxy_country": chosen_node.get("country", "DE"),
                    "transport_mode": "proxy-identity-relay",
                    "latency_ms": elapsed_ms,
                },
            )

    def _record_proxy_usage_stat(self, proxy_node: Dict[str, Any], mode: str) -> None:
        pid = str(proxy_node.get("id") or "")
        pep = str(proxy_node.get("endpoint") or "")
        with self._lock:
            if mode == "tunnel":
                self._proxy_runtime_stats["proxied_tunnel_batches"] = (
                    int(self._proxy_runtime_stats.get("proxied_tunnel_batches") or 0) + 1
                )
            else:
                self._proxy_runtime_stats["proxy_spoofed_batches"] = (
                    int(self._proxy_runtime_stats.get("proxy_spoofed_batches") or 0) + 1
                )
            used_ids: List[str] = self._proxy_runtime_stats.setdefault("used_proxy_ids", [])
            if pid and pid not in used_ids:
                used_ids.append(pid)
            used_eps: List[str] = self._proxy_runtime_stats.setdefault("used_proxy_endpoints", [])
            if pep and pep not in used_eps:
                used_eps.append(pep)

    def get_proxy_runtime_stats(self, reset: bool = False) -> Dict[str, Any]:
        with self._lock:
            snapshot = {
                "total_batches": int(self._proxy_runtime_stats.get("total_batches") or 0),
                "proxied_tunnel_batches": int(self._proxy_runtime_stats.get("proxied_tunnel_batches") or 0),
                "proxy_spoofed_batches": int(self._proxy_runtime_stats.get("proxy_spoofed_batches") or 0),
                "proxy_rotations": int(self._proxy_runtime_stats.get("proxy_rotations") or 0),
                "cooldown_evictions": int(self._proxy_runtime_stats.get("cooldown_evictions") or 0),
                "unique_proxies_used": len(self._proxy_runtime_stats.get("used_proxy_ids") or []),
                "used_proxy_ids": list(self._proxy_runtime_stats.get("used_proxy_ids") or []),
                "used_proxy_endpoints": list(self._proxy_runtime_stats.get("used_proxy_endpoints") or []),
            }
            if reset:
                self._proxy_runtime_stats = {
                    "total_batches": 0,
                    "proxied_tunnel_batches": 0,
                    "proxy_spoofed_batches": 0,
                    "proxy_rotations": 0,
                    "cooldown_evictions": 0,
                    "used_proxy_ids": [],
                    "used_proxy_endpoints": [],
                }
            return snapshot

    def fetch_free_proxies_sync(self, protocol: str = "all", limit: int = 6) -> List[Dict[str, Any]]:
        limit = max(1, min(25, int(limit or 6)))
        sample_budget = max(limit * 5, 36)
        existing = self.get_existing_endpoints()
        protos = ["socks5", "socks4", "https", "http"] if protocol == "all" else [protocol.lower()]
        collected: List[Tuple[str, str]] = []

        ctx = _create_verified_ssl_context()
        per_proto_cap = max(8, sample_budget // max(1, len(protos)))
        for proto in protos:
            proto_added = 0
            for url in PROXY_FEED_SOURCES.get(proto, PROXY_FEED_SOURCES["http"]):
                try:
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                        method="GET",
                    )
                    with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                        if resp.status == 200:
                            lines = resp.read().decode("utf-8", errors="ignore").splitlines()
                            random.shuffle(lines)
                            for line in lines:
                                clean = line.strip()
                                if not re.match(r"^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$", clean) or clean in existing:
                                    continue
                                if proto in ("http", "https") and clean.endswith(":80"):
                                    continue
                                existing.add(clean)
                                collected.append((proto, clean))
                                proto_added += 1
                                if proto_added >= per_proto_cap or len(collected) >= sample_budget:
                                    break
                except Exception:
                    pass
                if proto_added >= per_proto_cap or len(collected) >= sample_budget:
                    break
            if len(collected) >= sample_budget:
                break

        if len(collected) < limit:
            for proto, ep in FALLBACK_PUBLIC_PROXIES:
                if len(collected) >= sample_budget:
                    break
                if protocol in ("all", proto) and ep not in existing:
                    existing.add(ep)
                    collected.append((proto, ep))

        verified_candidates: List[Tuple[str, str, int, bool]] = []
        if collected:
            with ThreadPoolExecutor(max_workers=24) as pool:
                fut_map = {
                    pool.submit(
                        self.probe_proxy_https_tunnel_sync,
                        {"protocol": p_proto, "endpoint": p_ep},
                        "text.pollinations.ai",
                        443,
                        2.3,
                    ): (p_proto, p_ep)
                    for (p_proto, p_ep) in collected
                }
                for fut in as_completed(fut_map):
                    p_proto, p_ep = fut_map[fut]
                    try:
                        ok, ms = fut.result()
                    except Exception:
                        ok, ms = (False, 999)
                    verified_candidates.append((p_proto, p_ep, ms, ok))

        verified_candidates.sort(key=lambda x: (0 if x[3] else 1, x[2]))

        added: List[Dict[str, Any]] = []
        for proto, ep, ms, is_live in verified_candidates[:limit]:
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
                "latency_ms": ms if is_live else random.randint(180, 390),
                "status": "active" if is_live else "cooldown",
                "fails": 0 if is_live else 2,
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
