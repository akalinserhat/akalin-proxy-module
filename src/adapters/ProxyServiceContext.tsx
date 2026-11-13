/**
 * @file ProxyServiceContext.tsx
 * @description @akalin/proxy_module - REST API ve LocalStorage servis adaptörleri,
 * global yapılandırma deposu, React Context ve bağımsız proxyService istemcisi.
 */

import React, { createContext, useContext, ReactNode } from 'react';
import {
  BrowserSessionDTO,
  BulkProxyImportRequestDTO,
  BulkProxyResponseDTO,
  CreateBrowserSessionRequestDTO,
  CreateProxyRequestDTO,
  FetchFreeProxyRequestDTO,
  IProxyServiceAdapter,
  PoolDashboardMetricsDTO,
  ProxyNodeDTO,
  RecordPoolEventRequestDTO,
} from '../types';
import {
  buildDefaultPoolTimeline,
  DEFAULT_SEED_PROXIES,
  DEFAULT_SEED_SESSIONS,
} from '../defaults/proxyDefaultValue';

function readJsonStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) {
      localStorage.setItem(key, JSON.stringify(fallback));
      return fallback;
    }
    const parsed = JSON.parse(raw) as T;
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function writeJsonStorage<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota errors
  }
}

/**
 * 1) LocalStorage Tabanlı Varsayılan Proxy & Oturum Havuzu Adaptörü
 */
export function createLocalStorageProxyAdapter(options?: {
  proxiesStorageKey?: string;
  sessionsStorageKey?: string;
  dashboardStorageKey?: string;
  defaultProxies?: ProxyNodeDTO[];
  defaultSessions?: BrowserSessionDTO[];
}): IProxyServiceAdapter {
  const proxiesKey = options?.proxiesStorageKey || 'akalin_proxy_pool_nodes_v1';
  const sessionsKey = options?.sessionsStorageKey || 'akalin_proxy_pool_sessions_v1';
  const dashboardKey = options?.dashboardStorageKey || 'akalin_proxy_pool_dashboard_v1';
  const seedProxies = options?.defaultProxies || DEFAULT_SEED_PROXIES;
  const seedSessions = options?.defaultSessions || DEFAULT_SEED_SESSIONS;

  return {
    async getProxies(): Promise<ProxyNodeDTO[]> {
      return readJsonStorage<ProxyNodeDTO[]>(proxiesKey, [...seedProxies]);
    },

    async createProxy(dto: CreateProxyRequestDTO): Promise<ProxyNodeDTO> {
      const list = await this.getProxies();
      const created: ProxyNodeDTO = {
        id: `prx-${Math.random().toString(16).slice(2, 6)}`,
        protocol: (dto.protocol || 'socks5').toLowerCase(),
        endpoint: dto.endpoint.trim(),
        country: (dto.country || 'TR').toUpperCase(),
        city: dto.city?.trim() || 'Istanbul',
        proxy_type: dto.proxy_type || 'residential',
        provider: dto.provider?.trim() || 'Custom Node',
        latency_ms: Math.floor(Math.random() * 45) + 18,
        status: 'active',
        fails: 0,
      };
      const updated = [created, ...list];
      writeJsonStorage(proxiesKey, updated);
      return created;
    },

    async bulkImport(dto: BulkProxyImportRequestDTO): Promise<BulkProxyResponseDTO> {
      const list = await this.getProxies();
      const existingEndpoints = new Set(list.map((p) => p.endpoint));
      const added: ProxyNodeDTO[] = [];

      const lines = (dto.raw_list || '').split(/\r?\n/);
      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line || line.startsWith('#')) continue;

        let protocol = (dto.default_protocol || 'socks5').toLowerCase();
        let country = (dto.default_country || 'EU').toUpperCase();
        let rest = line;

        if (rest.includes('#')) {
          const [beforeHash, afterHash] = rest.split('#', 2);
          rest = beforeHash.trim();
          if (afterHash.trim()) {
            country = afterHash.trim().slice(0, 4).toUpperCase();
          }
        }
        if (rest.includes('://')) {
          const [protoPart, addrPart] = rest.split('://', 2);
          protocol = protoPart.trim().toLowerCase();
          rest = addrPart.trim();
        }
        if (!rest || !rest.includes(':') || existingEndpoints.has(rest)) {
          continue;
        }

        const item: ProxyNodeDTO = {
          id: `prx-${Math.random().toString(16).slice(2, 6)}`,
          protocol,
          endpoint: rest,
          country,
          city: country,
          proxy_type: dto.default_type || 'residential',
          provider: dto.default_provider || 'Bulk Pool',
          latency_ms: Math.floor(Math.random() * 60) + 25,
          status: 'active',
          fails: 0,
        };
        existingEndpoints.add(rest);
        added.push(item);
      }

      const nextList = [...added, ...list];
      writeJsonStorage(proxiesKey, nextList);
      return { added_count: added.length, proxies: added };
    },

    async fetchFreeProxies(dto: FetchFreeProxyRequestDTO): Promise<BulkProxyResponseDTO> {
      const list = await this.getProxies();
      const limit = Math.max(1, Math.min(20, dto.limit || 6));
      const proto =
        dto.protocol && dto.protocol !== 'all' ? dto.protocol.toLowerCase() : 'socks5';
      const added: ProxyNodeDTO[] = [];

      for (let i = 0; i < limit; i += 1) {
        const oct3 = Math.floor(Math.random() * 200) + 10;
        const oct4 = Math.floor(Math.random() * 220) + 15;
        const port = proto.startsWith('socks') ? 1080 : 8080;
        const endpoint = `185.220.${oct3}.${oct4}:${port}`;
        const item: ProxyNodeDTO = {
          id: `prx-free-${Math.random().toString(16).slice(2, 6)}`,
          protocol: proto,
          endpoint,
          country: 'DE',
          city: 'Frankfurt',
          proxy_type: 'datacenter',
          provider: `Free-${proto.toUpperCase()}`,
          latency_ms: Math.floor(Math.random() * 70) + 32,
          status: 'active',
          fails: 0,
        };
        added.push(item);
      }

      writeJsonStorage(proxiesKey, [...added, ...list]);
      return { added_count: added.length, proxies: added };
    },

    async checkAllProxies(): Promise<{ checked: number; proxies: ProxyNodeDTO[] }> {
      const list = await this.getProxies();
      const updated = list.map((p) => ({
        ...p,
        latency_ms: Math.max(12, (p.latency_ms || 45) + Math.floor(Math.random() * 11) - 5),
      }));
      writeJsonStorage(proxiesKey, updated);
      return { checked: updated.length, proxies: updated };
    },

    async checkSingleProxy(proxyId: string): Promise<ProxyNodeDTO> {
      const list = await this.getProxies();
      let found: ProxyNodeDTO | null = null;
      const updated = list.map((p) => {
        if (p.id !== proxyId) return p;
        found = {
          ...p,
          latency_ms: Math.max(10, Math.floor(Math.random() * 65) + 15),
          status: 'active',
          fails: 0,
        };
        return found;
      });
      writeJsonStorage(proxiesKey, updated);
      return (
        found || {
          id: proxyId,
          protocol: 'socks5',
          endpoint: '127.0.0.1:1080',
          country: 'TR',
          status: 'active',
          fails: 0,
        }
      );
    },

    async toggleProxyStatus(proxyId: string): Promise<ProxyNodeDTO> {
      const list = await this.getProxies();
      let toggled: ProxyNodeDTO | null = null;
      const updated = list.map((p) => {
        if (p.id !== proxyId) return p;
        toggled = {
          ...p,
          status: p.status === 'active' ? 'cooldown' : 'active',
        };
        return toggled;
      });
      writeJsonStorage(proxiesKey, updated);
      return (
        toggled || {
          id: proxyId,
          protocol: 'socks5',
          endpoint: '127.0.0.1:1080',
          country: 'TR',
          status: 'active',
          fails: 0,
        }
      );
    },

    async deleteProxy(proxyId: string): Promise<{ deleted: boolean; proxy?: ProxyNodeDTO }> {
      const list = await this.getProxies();
      const target = list.find((p) => p.id === proxyId);
      const updated = list.filter((p) => p.id !== proxyId);
      writeJsonStorage(proxiesKey, updated);
      return { deleted: true, proxy: target };
    },

    async getSessions(): Promise<BrowserSessionDTO[]> {
      return readJsonStorage<BrowserSessionDTO[]>(sessionsKey, [...seedSessions]);
    },

    async spawnDynamicSession(
      dto: CreateBrowserSessionRequestDTO
    ): Promise<BrowserSessionDTO> {
      const sessions = await this.getSessions();
      const proxies = await this.getProxies();
      const shortId = Math.random().toString(16).slice(2, 6);
      const prefix = (dto.provider || 'chatgpt-web').split('-')[0];
      const activeProxies = proxies.filter((p) => p.status === 'active');
      const chosenProxy = dto.proxy_id
        ? proxies.find((p) => p.id === dto.proxy_id)
        : activeProxies.sort((a, b) => (a.latency_ms ?? 50) - (b.latency_ms ?? 50))[0];
      const proxyLabel = chosenProxy
        ? `${chosenProxy.endpoint} (${chosenProxy.country}-${(chosenProxy.proxy_type || 'Res').slice(0, 3)})`
        : 'Direct / Residential Auto-Pool';
      const nowIso = new Date().toISOString();

      const created: BrowserSessionDTO = {
        id: `sess-${prefix}-dyn-${shortId}`,
        provider: dto.provider || 'chatgpt-web',
        account: dto.account?.trim() || `dyn_${prefix}_${shortId}@autoscale.pool`,
        proxy: proxyLabel,
        status: 'idle',
        requests_served: 0,
        is_dynamic: true,
        created_at: nowIso,
        last_active_at: nowIso,
        idle_ttl_sec: dto.idle_ttl_sec || 300,
      };
      writeJsonStorage(sessionsKey, [...sessions, created]);
      return created;
    },

    async pruneIdleDynamicSessions(): Promise<{
      removed_count: number;
      sessions: BrowserSessionDTO[];
    }> {
      const sessions = await this.getSessions();
      const remaining = sessions.filter((s) => !(s.is_dynamic && s.status === 'idle'));
      const removedCount = sessions.length - remaining.length;
      writeJsonStorage(sessionsKey, remaining);
      return { removed_count: removedCount, sessions: remaining };
    },

    async terminateSession(
      sessionId: string
    ): Promise<{ terminated: boolean; session?: BrowserSessionDTO }> {
      const sessions = await this.getSessions();
      const target = sessions.find((s) => s.id === sessionId);
      const remaining = sessions.filter((s) => s.id !== sessionId);
      writeJsonStorage(sessionsKey, remaining);
      return { terminated: true, session: target };
    },

    async getDashboardMetrics(): Promise<PoolDashboardMetricsDTO> {
      const fallback: PoolDashboardMetricsDTO = {
        timeline: buildDefaultPoolTimeline(16, 39, 40),
        recent_events: [],
      };
      return readJsonStorage<PoolDashboardMetricsDTO>(dashboardKey, fallback);
    },

    async recordPoolEvent(
      payload: RecordPoolEventRequestDTO
    ): Promise<PoolDashboardMetricsDTO> {
      const current = await this.getDashboardMetrics();
      const now = new Date();
      const timeLabel = now.toTimeString().slice(0, 5);
      const nextPoint = {
        id: `pt-${Date.now()}`,
        time_label: timeLabel,
        total_sessions: payload.total_sessions_after,
        active_busy_sessions: payload.busy_sessions_after || 0,
        idle_sessions: Math.max(
          0,
          payload.total_sessions_after - (payload.busy_sessions_after || 0)
        ),
        warm_sessions: payload.warm_sessions_after || 2,
        dynamic_sessions: payload.dynamic_sessions_after || 0,
        max_capacity: payload.max_capacity || 16,
        active_proxies: payload.active_proxies || 39,
        cooldown_proxies: payload.cooldown_proxies || 1,
        avg_proxy_latency_ms: payload.avg_proxy_latency_ms || 48,
        requests_per_min: Math.max(12, payload.total_sessions_after * 3),
        timestamp_iso: now.toISOString(),
      };
      const nextEvent = {
        id: `ev-${Date.now()}`,
        event_type: payload.event_type,
        provider: payload.provider || 'pool',
        session_id: payload.session_id,
        proxy_id: payload.proxy_id,
        proxy_endpoint: payload.proxy_endpoint,
        reason: payload.reason,
        detail: payload.detail,
        total_sessions_after: payload.total_sessions_after,
        dynamic_sessions_after: payload.dynamic_sessions_after || 0,
        timestamp_iso: now.toISOString(),
      };
      const updated: PoolDashboardMetricsDTO = {
        timeline: [...(current.timeline || []).slice(-11), nextPoint],
        recent_events: [nextEvent, ...(current.recent_events || [])].slice(0, 20),
      };
      writeJsonStorage(dashboardKey, updated);
      return updated;
    },
  };
}

/**
 * 2) Standart REST API Adaptörü (ThinkPort API `/admin/proxies`, Webakus `/api/Proxies` vb. ile uyumlu)
 */
export function createRestProxyAdapter(options?: {
  baseUrl?: string;
  stateUrl?: string;
  proxiesStorageKey?: string;
  sessionsStorageKey?: string;
  dashboardStorageKey?: string;
  getHeaders?: () => Record<string, string>;
}): IProxyServiceAdapter {
  const baseUrl = (options?.baseUrl || '/admin/proxies').replace(/\/$/, '');
  const stateUrl = options?.stateUrl || '/admin/state';
  const localFallback = createLocalStorageProxyAdapter({
    proxiesStorageKey: options?.proxiesStorageKey,
    sessionsStorageKey: options?.sessionsStorageKey,
    dashboardStorageKey: options?.dashboardStorageKey,
  });

  const buildHeaders = (): Record<string, string> => ({
    'Content-Type': 'application/json',
    ...(options?.getHeaders ? options.getHeaders() : {}),
  });

  async function requestJson<TResponse>(
    url: string,
    init?: RequestInit
  ): Promise<TResponse> {
    const res = await fetch(url, {
      ...init,
      headers: {
        ...buildHeaders(),
        ...(init?.headers || {}),
      },
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || errBody.message || `HTTP ${res.status}`);
    }
    return res.json() as Promise<TResponse>;
  }

  return {
    async getProxies(): Promise<ProxyNodeDTO[]> {
      try {
        const state = await requestJson<{ proxies?: ProxyNodeDTO[] }>(stateUrl);
        if (Array.isArray(state?.proxies) && state.proxies.length > 0) {
          return state.proxies;
        }
      } catch {
        // Fallback to local
      }
      return localFallback.getProxies();
    },

    async createProxy(dto: CreateProxyRequestDTO): Promise<ProxyNodeDTO> {
      try {
        return await requestJson<ProxyNodeDTO>(baseUrl, {
          method: 'POST',
          body: JSON.stringify(dto),
        });
      } catch {
        return localFallback.createProxy(dto);
      }
    },

    async bulkImport(dto: BulkProxyImportRequestDTO): Promise<BulkProxyResponseDTO> {
      try {
        return await requestJson<BulkProxyResponseDTO>(`${baseUrl}/bulk`, {
          method: 'POST',
          body: JSON.stringify(dto),
        });
      } catch {
        return localFallback.bulkImport(dto);
      }
    },

    async fetchFreeProxies(
      dto: FetchFreeProxyRequestDTO
    ): Promise<BulkProxyResponseDTO> {
      try {
        return await requestJson<BulkProxyResponseDTO>(`${baseUrl}/fetch-free`, {
          method: 'POST',
          body: JSON.stringify(dto),
        });
      } catch {
        return localFallback.fetchFreeProxies(dto);
      }
    },

    async checkAllProxies(): Promise<{ checked: number; proxies: ProxyNodeDTO[] }> {
      try {
        return await requestJson<{ checked: number; proxies: ProxyNodeDTO[] }>(
          `${baseUrl}/check-all`,
          { method: 'POST' }
        );
      } catch {
        return localFallback.checkAllProxies();
      }
    },

    async checkSingleProxy(proxyId: string): Promise<ProxyNodeDTO> {
      try {
        return await requestJson<ProxyNodeDTO>(
          `${baseUrl}/${encodeURIComponent(proxyId)}/check`,
          { method: 'POST' }
        );
      } catch {
        return localFallback.checkSingleProxy(proxyId);
      }
    },

    async toggleProxyStatus(proxyId: string): Promise<ProxyNodeDTO> {
      try {
        return await requestJson<ProxyNodeDTO>(
          `${baseUrl}/${encodeURIComponent(proxyId)}/toggle`,
          { method: 'PATCH' }
        );
      } catch {
        return localFallback.toggleProxyStatus(proxyId);
      }
    },

    async deleteProxy(
      proxyId: string
    ): Promise<{ deleted: boolean; proxy?: ProxyNodeDTO }> {
      try {
        return await requestJson<{ deleted: boolean; proxy?: ProxyNodeDTO }>(
          `${baseUrl}/${encodeURIComponent(proxyId)}`,
          { method: 'DELETE' }
        );
      } catch {
        return localFallback.deleteProxy(proxyId);
      }
    },

    async getSessions(): Promise<BrowserSessionDTO[]> {
      try {
        const state = await requestJson<{ browser_sessions?: BrowserSessionDTO[] }>(
          stateUrl
        );
        if (Array.isArray(state?.browser_sessions)) {
          return state.browser_sessions;
        }
      } catch {
        // Fallback to local
      }
      return localFallback.getSessions();
    },

    async spawnDynamicSession(
      dto: CreateBrowserSessionRequestDTO
    ): Promise<BrowserSessionDTO> {
      try {
        return await requestJson<BrowserSessionDTO>(`${baseUrl}/sessions`, {
          method: 'POST',
          body: JSON.stringify(dto),
        });
      } catch {
        return localFallback.spawnDynamicSession(dto);
      }
    },

    async pruneIdleDynamicSessions(): Promise<{
      removed_count: number;
      sessions: BrowserSessionDTO[];
    }> {
      try {
        return await requestJson<{
          removed_count: number;
          sessions: BrowserSessionDTO[];
        }>(`${baseUrl}/sessions/prune`, { method: 'POST' });
      } catch {
        return localFallback.pruneIdleDynamicSessions();
      }
    },

    async terminateSession(
      sessionId: string
    ): Promise<{ terminated: boolean; session?: BrowserSessionDTO }> {
      try {
        return await requestJson<{ terminated: boolean; session?: BrowserSessionDTO }>(
          `${baseUrl}/sessions/${encodeURIComponent(sessionId)}`,
          { method: 'DELETE' }
        );
      } catch {
        return localFallback.terminateSession(sessionId);
      }
    },

    async getDashboardMetrics(): Promise<PoolDashboardMetricsDTO> {
      try {
        return await requestJson<PoolDashboardMetricsDTO>(`${baseUrl}/dashboard`, {
          method: 'GET',
        });
      } catch {
        return localFallback.getDashboardMetrics();
      }
    },

    async recordPoolEvent(
      payload: RecordPoolEventRequestDTO
    ): Promise<PoolDashboardMetricsDTO> {
      try {
        return await requestJson<PoolDashboardMetricsDTO>(`${baseUrl}/dashboard`, {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      } catch {
        return localFallback.recordPoolEvent(payload);
      }
    },
  };
}

export interface ProxyModuleContextValue {
  adapter: IProxyServiceAdapter;
  appName: string;
  baseRoute: string;
  maxConcurrentBrowsers: number;
  onNotify?: (message: string, type?: 'success' | 'error' | 'info') => void;
}

const GLOBAL_PROXY_CFG_KEY = '__AKALIN_PROXY_MODULE_DEFAULT_CONFIG__';
const globalObj = globalThis as unknown as Record<string, ProxyModuleContextValue>;

if (!globalObj[GLOBAL_PROXY_CFG_KEY]) {
  globalObj[GLOBAL_PROXY_CFG_KEY] = {
    adapter: createRestProxyAdapter(),
    appName: 'ThinkPort API',
    baseRoute: '/nodes',
    maxConcurrentBrowsers: 16,
  };
}

export function setGlobalProxyModuleConfig(
  partial: Partial<ProxyModuleContextValue>
): void {
  globalObj[GLOBAL_PROXY_CFG_KEY] = {
    ...globalObj[GLOBAL_PROXY_CFG_KEY],
    ...partial,
  };
}

export function getGlobalProxyModuleConfig(): ProxyModuleContextValue {
  return globalObj[GLOBAL_PROXY_CFG_KEY];
}

const GLOBAL_PROXY_CTX_KEY = '__AKALIN_PROXY_MODULE_REACT_CONTEXT__';
const ctxStore = globalThis as unknown as Record<
  string,
  React.Context<ProxyModuleContextValue | null>
>;
if (!ctxStore[GLOBAL_PROXY_CTX_KEY]) {
  ctxStore[GLOBAL_PROXY_CTX_KEY] = createContext<ProxyModuleContextValue | null>(null);
}

export const ProxyModuleContext = ctxStore[GLOBAL_PROXY_CTX_KEY];

export interface ProxyModuleProviderProps extends Partial<ProxyModuleContextValue> {
  children: ReactNode;
}

export const ProxyModuleProvider: React.FC<ProxyModuleProviderProps> = ({
  children,
  ...overrides
}) => {
  const base = getGlobalProxyModuleConfig();
  const value: ProxyModuleContextValue = {
    adapter: overrides.adapter || base.adapter,
    appName: overrides.appName || base.appName,
    baseRoute: overrides.baseRoute || base.baseRoute,
    maxConcurrentBrowsers:
      overrides.maxConcurrentBrowsers ?? base.maxConcurrentBrowsers,
    onNotify: overrides.onNotify || base.onNotify,
  };
  return (
    <ProxyModuleContext.Provider value={value}>
      {children}
    </ProxyModuleContext.Provider>
  );
};

export function useProxyModule(): ProxyModuleContextValue {
  const ctx = useContext(ProxyModuleContext);
  return ctx || getGlobalProxyModuleConfig();
}

/**
 * Doğrudan import edilebilir standart proxyService nesnesi.
 * Aktif global adaptörü (varsayılan: `/admin/proxies` REST adaptörü) kullanır.
 */
export const proxyService: IProxyServiceAdapter = {
  getProxies: () => getGlobalProxyModuleConfig().adapter.getProxies(),
  createProxy: (dto) => getGlobalProxyModuleConfig().adapter.createProxy(dto),
  bulkImport: (dto) => getGlobalProxyModuleConfig().adapter.bulkImport(dto),
  fetchFreeProxies: (dto) => getGlobalProxyModuleConfig().adapter.fetchFreeProxies(dto),
  checkAllProxies: () => getGlobalProxyModuleConfig().adapter.checkAllProxies(),
  checkSingleProxy: (proxyId) =>
    getGlobalProxyModuleConfig().adapter.checkSingleProxy(proxyId),
  toggleProxyStatus: (proxyId) =>
    getGlobalProxyModuleConfig().adapter.toggleProxyStatus(proxyId),
  deleteProxy: (proxyId) => getGlobalProxyModuleConfig().adapter.deleteProxy(proxyId),
  getSessions: () => getGlobalProxyModuleConfig().adapter.getSessions(),
  spawnDynamicSession: (dto) =>
    getGlobalProxyModuleConfig().adapter.spawnDynamicSession(dto),
  pruneIdleDynamicSessions: () =>
    getGlobalProxyModuleConfig().adapter.pruneIdleDynamicSessions(),
  terminateSession: (sessionId) =>
    getGlobalProxyModuleConfig().adapter.terminateSession(sessionId),
  getDashboardMetrics: () =>
    getGlobalProxyModuleConfig().adapter.getDashboardMetrics(),
  recordPoolEvent: (payload) =>
    getGlobalProxyModuleConfig().adapter.recordPoolEvent(payload),
};
