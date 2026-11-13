/**
 * @file types.ts
 * @description @akalin/proxy_module - Proxy Havuzu, Dinamik Tarayıcı Oturumları (Auto-Scale)
 * ve Telemetri Dashboard Sözleşme Tipleri.
 */

export type ProxyProtocolType = 'http' | 'https' | 'socks4' | 'socks5';
export type ProxyCategoryType = 'residential' | 'mobile' | 'isp' | 'datacenter';
export type ProxyStatusType = 'active' | 'cooldown';
export type NodesPoolSection = 'dashboard' | 'sessions' | 'proxies';

export interface ProxyNodeDTO {
  id: string;
  protocol: string;
  endpoint: string;
  country: string;
  city?: string;
  proxy_type?: ProxyCategoryType | string;
  provider?: string;
  latency_ms?: number;
  status: ProxyStatusType | string;
  fails: number;
}

export interface CreateProxyRequestDTO {
  protocol: string;
  endpoint: string;
  country: string;
  city?: string;
  proxy_type?: string;
  provider?: string;
}

export interface BulkProxyImportRequestDTO {
  raw_list: string;
  default_protocol?: string;
  default_country?: string;
  default_type?: string;
  default_provider?: string;
}

export interface FetchFreeProxyRequestDTO {
  protocol?: string;
  limit?: number;
}

export interface BulkProxyResponseDTO {
  added_count: number;
  proxies: ProxyNodeDTO[];
}

export interface BrowserSessionDTO {
  id: string;
  provider: string;
  account: string;
  proxy: string;
  status: string;
  requests_served: number;
  is_dynamic?: boolean;
  created_at?: string;
  last_active_at?: string;
  idle_ttl_sec?: number;
}

export interface CreateBrowserSessionRequestDTO {
  provider: string;
  account?: string;
  proxy_id?: string;
  idle_ttl_sec?: number;
}

export interface PoolTimelinePointDTO {
  id?: string | number;
  time_label: string;
  total_sessions: number;
  active_busy_sessions: number;
  idle_sessions: number;
  warm_sessions: number;
  dynamic_sessions: number;
  max_capacity: number;
  active_proxies: number;
  cooldown_proxies: number;
  avg_proxy_latency_ms: number;
  requests_per_min: number;
  timestamp_iso?: string;
  created_at?: string;
}

export interface PoolScalingEventDTO {
  id: string;
  event_type:
    | 'scale_up'
    | 'scale_down'
    | 'proxy_rotate'
    | 'health_check'
    | 'autoscale_up'
    | 'autoscale_down'
    | 'manual_spawn'
    | 'session_terminated'
    | 'proxy_cooldown'
    | string;
  provider: string;
  session_id?: string;
  proxy_id?: string;
  proxy_endpoint?: string;
  reason?: string;
  detail?: string;
  total_sessions_after: number;
  dynamic_sessions_after: number;
  timestamp_iso?: string;
  created_at?: string;
}

export interface PoolDashboardMetricsDTO {
  timeline: PoolTimelinePointDTO[];
  scaling_events?: PoolScalingEventDTO[];
  recent_events?: PoolScalingEventDTO[];
  summary?: {
    total_sessions: number;
    warm_sessions: number;
    dynamic_sessions: number;
    busy_sessions: number;
    idle_sessions: number;
    max_capacity: number;
    utilization_pct: number;
    active_proxies: number;
    total_proxies: number;
    cooldown_proxies: number;
    avg_proxy_latency_ms: number;
    total_requests_served: number;
    autoscale_events_24h: number;
  };
}

export interface RecordPoolEventRequestDTO {
  event_type: string;
  provider?: string;
  session_id?: string;
  proxy_id?: string;
  proxy_endpoint?: string;
  reason?: string;
  detail?: string;
  total_sessions_after: number;
  dynamic_sessions_after?: number;
  warm_sessions_after?: number;
  busy_sessions_after?: number;
  max_capacity?: number;
  active_proxies?: number;
  cooldown_proxies?: number;
  avg_proxy_latency_ms?: number;
}

export interface IProxyServiceAdapter {
  getProxies(): Promise<ProxyNodeDTO[]>;
  createProxy(dto: CreateProxyRequestDTO): Promise<ProxyNodeDTO>;
  bulkImport(dto: BulkProxyImportRequestDTO): Promise<BulkProxyResponseDTO>;
  fetchFreeProxies(dto: FetchFreeProxyRequestDTO): Promise<BulkProxyResponseDTO>;
  checkAllProxies(): Promise<{ checked: number; proxies: ProxyNodeDTO[] }>;
  checkSingleProxy(proxyId: string): Promise<ProxyNodeDTO>;
  toggleProxyStatus(proxyId: string): Promise<ProxyNodeDTO>;
  deleteProxy(proxyId: string): Promise<{ deleted: boolean; proxy?: ProxyNodeDTO }>;
  getSessions(): Promise<BrowserSessionDTO[]>;
  spawnDynamicSession(dto: CreateBrowserSessionRequestDTO): Promise<BrowserSessionDTO>;
  pruneIdleDynamicSessions(): Promise<{
    removed_count: number;
    sessions: BrowserSessionDTO[];
  }>;
  terminateSession(sessionId: string): Promise<{
    terminated: boolean;
    session?: BrowserSessionDTO;
  }>;
  getDashboardMetrics(): Promise<PoolDashboardMetricsDTO>;
  recordPoolEvent(payload: RecordPoolEventRequestDTO): Promise<PoolDashboardMetricsDTO>;
}

export interface NodesPoolViewProps {
  activeSection?: NodesPoolSection;
  sessions?: BrowserSessionDTO[];
  proxies?: ProxyNodeDTO[];
  poolDashboard?: PoolDashboardMetricsDTO;
  maxConcurrentBrowsers?: number;
  onNavigateSection?: (sub: NodesPoolSection) => void;
  onToggleProxy?: (proxyId: string) => Promise<void>;
  onSpawnDynamicSession?: (req: CreateBrowserSessionRequestDTO) => Promise<void>;
  onPruneDynamicSessions?: () => Promise<void>;
  onTerminateSession?: (sessionId: string) => Promise<void>;
  onRefreshState?: () => Promise<void>;
  onShowToast?: (msg: string) => void;
}

export interface CreateProxyModuleOptions {
  /** Modül benzersiz kimliği (Varsayılan: 'proxy-module') */
  id?: string;
  /** Uygulama adı (Varsayılan: 'ThinkPort API') */
  appName?: string;
  /** Bağlantı ve Proxy Havuzu temel rotası (Varsayılan: '/nodes') */
  baseRoute?: string;
  /** Sistem Ayarları (BaseSystemPage) içindeki kart ID'si (Varsayılan: 'proxies') */
  settingsModuleId?: string;
  /** Sistem Ayarları kart başlığı */
  settingsModuleName?: string;
  /** Sistem Ayarları kart açıklaması */
  settingsModuleDesc?: string;
  /** Sistem Ayarları kart rozeti */
  settingsModuleBadge?: string;
  /** Sistem Ayarları kart sıralaması (Varsayılan: 50) */
  settingsOrder?: number;
  /** Menü sıralaması (Varsayılan: 50) */
  order?: number;
  /** Maksimum eşzamanlı tarayıcı kapasitesi (Varsayılan: 16) */
  maxConcurrentBrowsers?: number;
  /** Özel backend servis adaptörü */
  adapter?: IProxyServiceAdapter;
  /** Bildirim/Toast geri çağrısı */
  onNotify?: (message: string, type?: 'success' | 'error' | 'info') => void;
}
