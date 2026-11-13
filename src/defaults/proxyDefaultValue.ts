/**
 * @file proxyDefaultValue.ts
 * @description @akalin/proxy_module - Proxy ve Dinamik Tarayıcı Oturum Formları için
 * modül seviyesi başlangıç değerleri, seçenek listeleri ve varsayılan çekirdek veriler.
 */

import {
  BrowserSessionDTO,
  PoolTimelinePointDTO,
  ProxyNodeDTO,
} from '../types';

export interface SingleProxyFormState {
  protocol: string;
  endpoint: string;
  country: string;
  city: string;
  proxyType: string;
  provider: string;
}

export interface BulkProxyFormState {
  bulkList: string;
  bulkProtocol: string;
  bulkCountry: string;
  bulkType: string;
}

export interface SpawnSessionFormState {
  spawnProvider: string;
  spawnAccount: string;
  spawnProxyId: string;
  spawnIdleTtl: number;
}

export function getSingleProxyDefaultValues(): SingleProxyFormState {
  return {
    protocol: 'socks5',
    endpoint: '',
    country: 'TR',
    city: 'Istanbul',
    proxyType: 'residential',
    provider: 'Custom Residential',
  };
}

export function getBulkProxyDefaultValues(): BulkProxyFormState {
  return {
    bulkList: '',
    bulkProtocol: 'socks5',
    bulkCountry: 'EU',
    bulkType: 'residential',
  };
}

export function getSpawnSessionDefaultValues(): SpawnSessionFormState {
  return {
    spawnProvider: 'chatgpt-web',
    spawnAccount: '',
    spawnProxyId: '',
    spawnIdleTtl: 300,
  };
}

export const PROXY_PROTOCOL_OPTIONS = [
  { id: 'socks5', value: 'socks5', label: 'SOCKS5' },
  { id: 'https', value: 'https', label: 'HTTPS (SSL)' },
  { id: 'http', value: 'http', label: 'HTTP' },
  { id: 'socks4', value: 'socks4', label: 'SOCKS4' },
];

export const PROXY_COUNTRY_OPTIONS = [
  { id: 'TR', value: 'TR', label: 'TR — Türkiye' },
  { id: 'DE', value: 'DE', label: 'DE — Germany' },
  { id: 'US', value: 'US', label: 'US — United States' },
  { id: 'NL', value: 'NL', label: 'NL — Netherlands' },
  { id: 'GB', value: 'GB', label: 'GB — United Kingdom' },
  { id: 'FR', value: 'FR', label: 'FR — France' },
  { id: 'CH', value: 'CH', label: 'CH — Switzerland' },
  { id: 'JP', value: 'JP', label: 'JP — Japan' },
  { id: 'SG', value: 'SG', label: 'SG — Singapore' },
  { id: 'CA', value: 'CA', label: 'CA — Canada' },
  { id: 'SE', value: 'SE', label: 'SE — Sweden' },
  { id: 'FI', value: 'FI', label: 'FI — Finland' },
  { id: 'PL', value: 'PL', label: 'PL — Poland' },
  { id: 'AT', value: 'AT', label: 'AT — Austria' },
  { id: 'IT', value: 'IT', label: 'IT — Italy' },
  { id: 'ES', value: 'ES', label: 'ES — Spain' },
];

export const SPAWN_PROVIDER_OPTIONS = [
  { id: 'chatgpt-web', value: 'chatgpt-web', label: 'chatgpt-web — OpenAI ChatGPT Web' },
  { id: 'claude-web', value: 'claude-web', label: 'claude-web — Anthropic Claude Web' },
  { id: 'deepseek-web', value: 'deepseek-web', label: 'deepseek-web — DeepSeek R1 Web' },
  { id: 'gemini-web', value: 'gemini-web', label: 'gemini-web — Google Gemini Web' },
  { id: 'pollinations-image', value: 'pollinations-image', label: 'pollinations-image — Image Pool' },
];

export const DEFAULT_SEED_SESSIONS: BrowserSessionDTO[] = [
  {
    id: 'sess-gpt-01',
    provider: 'chatgpt-web',
    account: 'pool_gpt_01@domain.com',
    proxy: '194.36.110.12:8080 (TR-Res)',
    status: 'idle',
    requests_served: 142,
  },
  {
    id: 'sess-claude-01',
    provider: 'claude-web',
    account: 'pool_claude_01@domain.com',
    proxy: '176.88.19.204:1080 (US-SOCKS5)',
    status: 'idle',
    requests_served: 67,
  },
];

export const DEFAULT_SEED_PROXIES: ProxyNodeDTO[] = [
  { id: 'prx-01', protocol: 'http', endpoint: '194.36.110.12:8080', country: 'TR', city: 'Istanbul', proxy_type: 'residential', provider: 'TurkNet Res', latency_ms: 14, status: 'active', fails: 0 },
  { id: 'prx-02', protocol: 'socks5', endpoint: '88.255.140.28:1080', country: 'TR', city: 'Ankara', proxy_type: 'mobile', provider: 'TR 5G Mobile', latency_ms: 21, status: 'active', fails: 0 },
  { id: 'prx-03', protocol: 'https', endpoint: '85.105.42.91:8080', country: 'DE', city: 'Frankfurt', proxy_type: 'residential', provider: 'BrightData EU', latency_ms: 38, status: 'active', fails: 0 },
  { id: 'prx-04', protocol: 'socks5', endpoint: '138.201.92.14:1080', country: 'DE', city: 'Berlin', proxy_type: 'isp', provider: 'DE-CIX Static', latency_ms: 42, status: 'active', fails: 0 },
  { id: 'prx-05', protocol: 'socks5', endpoint: '176.88.19.204:1080', country: 'US', city: 'New York', proxy_type: 'residential', provider: 'Oxylabs US', latency_ms: 96, status: 'active', fails: 1 },
  { id: 'prx-06', protocol: 'https', endpoint: '64.225.88.110:8443', country: 'US', city: 'Los Angeles', proxy_type: 'mobile', provider: 'T-Mobile 5G', latency_ms: 134, status: 'active', fails: 0 },
  { id: 'prx-07', protocol: 'socks5', endpoint: '198.51.100.77:1080', country: 'US', city: 'Ashburn', proxy_type: 'isp', provider: 'Smartproxy ISP', latency_ms: 89, status: 'active', fails: 0 },
  { id: 'prx-08', protocol: 'http', endpoint: '91.93.120.44:8080', country: 'NL', city: 'Amsterdam', proxy_type: 'residential', provider: 'IPRoyal NL', latency_ms: 47, status: 'cooldown', fails: 3 },
  { id: 'prx-09', protocol: 'https', endpoint: '185.220.101.5:8443', country: 'GB', city: 'London', proxy_type: 'residential', provider: 'SOAX UK', latency_ms: 54, status: 'active', fails: 0 },
  { id: 'prx-10', protocol: 'socks5', endpoint: '51.158.118.42:1080', country: 'FR', city: 'Paris', proxy_type: 'isp', provider: 'Scaleway FR', latency_ms: 49, status: 'active', fails: 0 },
  { id: 'prx-11', protocol: 'https', endpoint: '179.43.148.19:8443', country: 'CH', city: 'Zurich', proxy_type: 'residential', provider: 'SwissPrivacy', latency_ms: 44, status: 'active', fails: 0 },
  { id: 'prx-12', protocol: 'socks5', endpoint: '45.76.210.88:1080', country: 'JP', city: 'Tokyo', proxy_type: 'residential', provider: 'NTT Japan', latency_ms: 168, status: 'active', fails: 0 },
  { id: 'prx-13', protocol: 'http', endpoint: '128.199.180.52:8080', country: 'SG', city: 'Singapore', proxy_type: 'datacenter', provider: 'SingTel DC', latency_ms: 152, status: 'active', fails: 0 },
  { id: 'prx-14', protocol: 'socks4', endpoint: '159.203.24.91:1080', country: 'CA', city: 'Toronto', proxy_type: 'residential', provider: 'Bell Canada', latency_ms: 108, status: 'active', fails: 0 },
  { id: 'prx-15', protocol: 'https', endpoint: '193.138.218.60:8443', country: 'SE', city: 'Stockholm', proxy_type: 'residential', provider: 'Mullvad SE', latency_ms: 59, status: 'active', fails: 0 },
  { id: 'prx-16', protocol: 'socks5', endpoint: '95.216.144.33:1080', country: 'FI', city: 'Helsinki', proxy_type: 'datacenter', provider: 'NordNode FI', latency_ms: 62, status: 'active', fails: 0 },
  { id: 'prx-17', protocol: 'socks5', endpoint: '145.220.227.208:8080', country: 'NL', city: 'Rotterdam', proxy_type: 'residential', provider: 'KPN Fiber NL', latency_ms: 45, status: 'active', fails: 0 },
  { id: 'prx-18', protocol: 'socks5', endpoint: '49.13.162.163:1081', country: 'DE', city: 'Nuremberg', proxy_type: 'datacenter', provider: 'Hetzner Cloud DE', latency_ms: 36, status: 'active', fails: 0 },
  { id: 'prx-19', protocol: 'socks5', endpoint: '212.47.71.179:9167', country: 'FR', city: 'Marseille', proxy_type: 'isp', provider: 'OnlineSAS FR', latency_ms: 48, status: 'active', fails: 0 },
  { id: 'prx-20', protocol: 'socks5', endpoint: '185.151.86.121:3699', country: 'GB', city: 'Manchester', proxy_type: 'residential', provider: 'BT Broadband UK', latency_ms: 56, status: 'active', fails: 0 },
  { id: 'prx-21', protocol: 'socks5', endpoint: '192.252.215.5:16137', country: 'US', city: 'Chicago', proxy_type: 'residential', provider: 'Comcast Xfinity', latency_ms: 104, status: 'active', fails: 0 },
  { id: 'prx-22', protocol: 'socks5', endpoint: '208.102.51.6:58208', country: 'US', city: 'Dallas', proxy_type: 'mobile', provider: 'AT&T 5G US', latency_ms: 118, status: 'active', fails: 0 },
  { id: 'prx-23', protocol: 'socks5', endpoint: '142.54.237.34:4145', country: 'US', city: 'Kansas City', proxy_type: 'isp', provider: 'Wholesale ISP', latency_ms: 112, status: 'active', fails: 0 },
  { id: 'prx-24', protocol: 'socks5', endpoint: '184.170.245.148:4145', country: 'US', city: 'Phoenix', proxy_type: 'residential', provider: 'Cox Residential', latency_ms: 127, status: 'active', fails: 0 },
  { id: 'prx-25', protocol: 'http', endpoint: '91.107.143.251:80', country: 'DE', city: 'Falkenstein', proxy_type: 'datacenter', provider: 'Hetzner Edge', latency_ms: 39, status: 'active', fails: 0 },
  { id: 'prx-26', protocol: 'http', endpoint: '137.74.50.101:15054', country: 'PL', city: 'Warsaw', proxy_type: 'isp', provider: 'OVH Poland', latency_ms: 51, status: 'active', fails: 0 },
  { id: 'prx-27', protocol: 'https', endpoint: '82.69.119.68:49200', country: 'GB', city: 'Bristol', proxy_type: 'residential', provider: 'Virgin Media UK', latency_ms: 58, status: 'active', fails: 0 },
  { id: 'prx-28', protocol: 'http', endpoint: '195.114.209.50:80', country: 'PL', city: 'Krakow', proxy_type: 'residential', provider: 'Orange Polska', latency_ms: 53, status: 'active', fails: 0 },
  { id: 'prx-29', protocol: 'https', endpoint: '5.45.126.128:8080', country: 'AT', city: 'Vienna', proxy_type: 'isp', provider: 'A1 Telekom AT', latency_ms: 41, status: 'active', fails: 0 },
  { id: 'prx-30', protocol: 'http', endpoint: '174.138.119.88:80', country: 'CA', city: 'Montreal', proxy_type: 'datacenter', provider: 'DigitalOcean CA', latency_ms: 102, status: 'active', fails: 0 },
  { id: 'prx-31', protocol: 'socks5', endpoint: '8.219.94.23:7890', country: 'SG', city: 'Jurong', proxy_type: 'datacenter', provider: 'Alibaba Cloud SG', latency_ms: 146, status: 'active', fails: 0 },
  { id: 'prx-32', protocol: 'socks5', endpoint: '193.200.85.129:1081', country: 'IT', city: 'Milan', proxy_type: 'residential', provider: 'Fastweb IT', latency_ms: 46, status: 'active', fails: 0 },
  { id: 'prx-33', protocol: 'socks5', endpoint: '146.19.143.200:1081', country: 'ES', city: 'Madrid', proxy_type: 'residential', provider: 'Telefonica ES', latency_ms: 61, status: 'active', fails: 0 },
  { id: 'prx-34', protocol: 'socks4', endpoint: '149.248.201.109:9000', country: 'CH', city: 'Geneva', proxy_type: 'isp', provider: 'Swisscom ISP', latency_ms: 45, status: 'active', fails: 0 },
  { id: 'prx-35', protocol: 'socks4', endpoint: '72.195.34.41:4145', country: 'US', city: 'Seattle', proxy_type: 'residential', provider: 'Verizon Fios', latency_ms: 129, status: 'active', fails: 0 },
  { id: 'prx-36', protocol: 'socks4', endpoint: '66.42.224.229:41679', country: 'JP', city: 'Osaka', proxy_type: 'datacenter', provider: 'Vultr Osaka', latency_ms: 162, status: 'active', fails: 0 },
  { id: 'prx-37', protocol: 'socks4', endpoint: '46.101.148.225:10000', country: 'GB', city: 'London', proxy_type: 'datacenter', provider: 'LON1 Edge', latency_ms: 52, status: 'active', fails: 0 },
  { id: 'prx-38', protocol: 'socks4', endpoint: '167.99.3.26:11080', country: 'NL', city: 'Amsterdam', proxy_type: 'datacenter', provider: 'AMS3 Core', latency_ms: 43, status: 'active', fails: 0 },
  { id: 'prx-39', protocol: 'https', endpoint: '212.156.98.44:8443', country: 'TR', city: 'Izmir', proxy_type: 'residential', provider: 'TurkTelekom Fiber', latency_ms: 19, status: 'active', fails: 0 },
  { id: 'prx-40', protocol: 'socks5', endpoint: '176.240.112.75:1080', country: 'TR', city: 'Bursa', proxy_type: 'mobile', provider: 'Vodafone TR 5G', latency_ms: 23, status: 'active', fails: 0 },
];

export function buildDefaultPoolTimeline(
  maxConcurrentBrowsers = 16,
  activeCount = 39,
  totalProxies = 40
): PoolTimelinePointDTO[] {
  const cooldownCount = Math.max(0, totalProxies - activeCount);
  return [
    {
      id: '1',
      time_label: '19:35',
      total_sessions: 9,
      active_busy_sessions: 2,
      idle_sessions: 7,
      warm_sessions: 9,
      dynamic_sessions: 0,
      max_capacity: maxConcurrentBrowsers,
      active_proxies: activeCount,
      cooldown_proxies: cooldownCount,
      avg_proxy_latency_ms: 74,
      requests_per_min: 18,
      timestamp_iso: '',
    },
    {
      id: '2',
      time_label: '19:45',
      total_sessions: 11,
      active_busy_sessions: 6,
      idle_sessions: 5,
      warm_sessions: 9,
      dynamic_sessions: 2,
      max_capacity: maxConcurrentBrowsers,
      active_proxies: activeCount,
      cooldown_proxies: cooldownCount,
      avg_proxy_latency_ms: 78,
      requests_per_min: 42,
      timestamp_iso: '',
    },
    {
      id: '3',
      time_label: '19:55',
      total_sessions: 14,
      active_busy_sessions: 10,
      idle_sessions: 4,
      warm_sessions: 9,
      dynamic_sessions: 5,
      max_capacity: maxConcurrentBrowsers,
      active_proxies: activeCount,
      cooldown_proxies: cooldownCount,
      avg_proxy_latency_ms: 84,
      requests_per_min: 61,
      timestamp_iso: '',
    },
    {
      id: '4',
      time_label: '20:05',
      total_sessions: 12,
      active_busy_sessions: 7,
      idle_sessions: 5,
      warm_sessions: 9,
      dynamic_sessions: 3,
      max_capacity: maxConcurrentBrowsers,
      active_proxies: activeCount,
      cooldown_proxies: cooldownCount,
      avg_proxy_latency_ms: 76,
      requests_per_min: 45,
      timestamp_iso: '',
    },
    {
      id: '5',
      time_label: '20:15',
      total_sessions: 10,
      active_busy_sessions: 4,
      idle_sessions: 6,
      warm_sessions: 9,
      dynamic_sessions: 1,
      max_capacity: maxConcurrentBrowsers,
      active_proxies: activeCount,
      cooldown_proxies: cooldownCount,
      avg_proxy_latency_ms: 73,
      requests_per_min: 30,
      timestamp_iso: '',
    },
  ];
}
