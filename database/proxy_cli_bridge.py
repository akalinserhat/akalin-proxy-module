"""
@akalin/proxy_module - Bağımsız PostgreSQL (`akalin_proxy_db`) JSON CLI Köprüsü (proxy_cli_bridge.py).
Node.js, Vite, FastAPI, .NET veya CLI süreçlerinden stdin/stdout JSON protokolü ile
doğrudan `akalin_proxy_db` veritabanı üzerinde işlem yapılmasını sağlar.
"""
from __future__ import annotations
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict

_db_path = Path(__file__).resolve().parent / "proxy_postgres_db.py"
_db_spec = importlib.util.spec_from_file_location("akalin_proxy_postgres_db", str(_db_path))
assert _db_spec and _db_spec.loader
_db_mod = importlib.util.module_from_spec(_db_spec)
_db_spec.loader.exec_module(_db_mod)
proxy_db = _db_mod.proxy_db


def handle_action(req: Dict[str, Any]) -> Any:
    action = str(req.get("action") or "").strip()
    body = req.get("body") or req.get("payload") or {}

    if action in ("list_proxies", "proxies_list"):
        return proxy_db.list_proxies()

    if action in ("create_proxy", "proxies_create"):
        endpoint = str(body.get("endpoint") or "").strip()
        protocol = str(body.get("protocol") or "socks5").strip().lower()
        if "://" in endpoint:
            scheme, rest = endpoint.split("://", 1)
            if scheme.lower() in ("http", "https", "socks4", "socks5"):
                protocol = scheme.lower()
            endpoint = rest.strip()
        latency_ms = proxy_db.probe_proxy_latency_sync(endpoint)
        node = {
            "id": f"prx-{uuid.uuid4().hex[:5]}",
            "protocol": protocol,
            "endpoint": endpoint,
            "country": str(body.get("country") or "TR").upper()[:4],
            "city": str(body.get("city") or "Custom"),
            "proxy_type": str(body.get("proxy_type") or "residential"),
            "provider": str(body.get("provider") or "Custom Node"),
            "latency_ms": latency_ms,
            "status": "active",
            "fails": 0,
        }
        return proxy_db.insert_proxy(node)

    if action in ("bulk_import_proxies", "proxies_bulk_import"):
        raw_list = str(body.get("raw_list") or "")
        default_proto = str(body.get("default_protocol") or "socks5").lower()
        default_country = str(body.get("default_country") or "EU").upper()[:4]
        default_type = str(body.get("default_type") or "datacenter")
        default_provider = str(body.get("default_provider") or "Bulk Import")
        existing = proxy_db.get_existing_endpoints()
        added = []
        for raw_line in raw_list.splitlines()[:100]:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            proto = default_proto
            country = default_country
            if "#" in line:
                line, tag = line.split("#", 1)
                if tag.strip():
                    country = tag.strip().upper()[:4]
            if "://" in line:
                scheme, rest = line.split("://", 1)
                if scheme.lower() in ("http", "https", "socks4", "socks5"):
                    proto = scheme.lower()
                line = rest.strip()
            if not line or ":" not in line or line in existing:
                continue
            existing.add(line)
            saved = proxy_db.insert_proxy({
                "id": f"prx-{uuid.uuid4().hex[:5]}",
                "protocol": proto,
                "endpoint": line,
                "country": country,
                "city": "Imported",
                "proxy_type": default_type,
                "provider": default_provider,
                "latency_ms": 48,
                "status": "active",
                "fails": 0,
            })
            added.append(saved)
        return {"added_count": len(added), "added": added, "proxies": added}

    if action in ("fetch_free_proxies", "proxies_fetch_free"):
        protocol = str(body.get("protocol") or "all")
        limit = int(body.get("limit") or 6)
        added = proxy_db.fetch_free_proxies_sync(protocol=protocol, limit=limit)
        return {"added_count": len(added), "added": added, "proxies": added}

    if action in ("check_all_proxies", "proxies_check_all"):
        proxies = proxy_db.list_proxies()
        for p in proxies:
            ms = proxy_db.probe_proxy_latency_sync(p["endpoint"])
            new_status = "active" if int(p.get("fails") or 0) == 0 else None
            proxy_db.update_proxy_health(p["id"], latency_ms=ms, status=new_status)
        updated = proxy_db.list_proxies()
        return {"checked": len(updated), "proxies": updated}

    if action in ("check_single_proxy", "proxies_check_one"):
        proxy_id = str(req.get("proxy_id") or body.get("proxy_id") or "")
        target = proxy_db.get_proxy_by_id(proxy_id)
        if not target:
            return {"error": "Proxy bulunamadı"}
        ms = proxy_db.probe_proxy_latency_sync(target["endpoint"])
        return proxy_db.update_proxy_health(
            proxy_id, latency_ms=ms, status="active", reset_fails=True
        )

    if action in ("toggle_proxy_status", "proxies_toggle"):
        proxy_id = str(req.get("proxy_id") or body.get("proxy_id") or "")
        target = proxy_db.get_proxy_by_id(proxy_id)
        if not target:
            return {"error": "Proxy bulunamadı"}
        next_status = "cooldown" if target.get("status") == "active" else "active"
        return proxy_db.update_proxy_health(
            proxy_id,
            latency_ms=int(target.get("latency_ms") or 45),
            status=next_status,
            reset_fails=(next_status == "active"),
        )

    if action in ("delete_proxy", "proxies_delete"):
        proxy_id = str(req.get("proxy_id") or body.get("proxy_id") or "")
        removed = proxy_db.delete_proxy_by_id(proxy_id)
        if not removed:
            return {"error": "Proxy bulunamadı"}
        return {"deleted": True, "proxy": removed}

    if action in ("list_sessions", "sessions_list"):
        return proxy_db.list_sessions()

    if action in ("spawn_session", "sessions_spawn"):
        return proxy_db.spawn_dynamic_session(
            provider=str(body.get("provider") or "chatgpt-web"),
            account=str(body.get("account") or ""),
            proxy_id=str(body.get("proxy_id") or ""),
            idle_ttl_sec=int(body.get("idle_ttl_sec") or 300),
            is_dynamic=True,
        )

    if action in ("prune_sessions", "sessions_prune_idle"):
        removed_count = proxy_db.prune_idle_dynamic_sessions()
        return {
            "removed_count": removed_count,
            "sessions": proxy_db.list_sessions(),
        }

    if action in ("terminate_session", "sessions_terminate"):
        session_id = str(req.get("session_id") or body.get("session_id") or "")
        removed = proxy_db.terminate_session(session_id)
        if not removed:
            return {"error": "Tarayıcı oturumu bulunamadı"}
        return {"terminated": True, "session": removed}

    if action == "pool_dashboard":
        return proxy_db.get_pool_dashboard_metrics()

    if action == "record_pool_event":
        now_dt = datetime.now(timezone.utc)
        time_label = (now_dt + timedelta(hours=3)).strftime("%H:%M:%S")
        event_type = str(body.get("event_type") or "scale_up")
        provider = str(body.get("provider") or "chatgpt-web")
        session_id = str(body.get("session_id") or f"sess_{uuid.uuid4().hex[:6]}")
        proxy_ep = str(body.get("proxy_endpoint") or body.get("proxy_id") or "auto-proxy")
        detail = str(body.get("detail") or body.get("reason") or "Havuz ölçeklenme işlemi")
        total_after = int(body.get("total_sessions_after") or 9)
        dyn_after = int(body.get("dynamic_sessions_after") or 0)
        warm_after = int(body.get("warm_sessions_after") or max(0, total_after - dyn_after))
        busy_after = int(body.get("busy_sessions_after") or 0)
        idle_after = max(0, total_after - busy_after)
        max_cap = int(body.get("max_capacity") or 16)
        act_proxies = int(body.get("active_proxies") or 39)
        cool_proxies = int(body.get("cooldown_proxies") or 1)
        avg_lat = int(body.get("avg_proxy_latency_ms") or 72)
        rpm_est = max(12, busy_after * 7 + total_after * 2)

        with proxy_db.connection() as conn:
            conn.execute(
                """
                INSERT INTO pool_scaling_events (
                    id, event_type, session_id, provider,
                    proxy_endpoint, detail, total_sessions_after, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"evt_{uuid.uuid4().hex[:12]}",
                    event_type,
                    session_id,
                    provider,
                    proxy_ep,
                    detail,
                    total_after,
                    now_dt.isoformat(),
                ),
            )
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
                    f"snap_{uuid.uuid4().hex[:12]}",
                    now_dt.isoformat(),
                    time_label,
                    total_after,
                    busy_after,
                    idle_after,
                    warm_after,
                    dyn_after,
                    max_cap,
                    act_proxies,
                    cool_proxies,
                    avg_lat,
                    rpm_est,
                ),
            )
        return proxy_db.get_pool_dashboard_metrics(max_capacity=max_cap)

    return {"error": f"Unknown action: {action}"}


def main() -> None:
    raw = sys.stdin.read().strip()
    req = json.loads(raw) if raw else {}
    res = handle_action(req)
    sys.stdout.write(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
