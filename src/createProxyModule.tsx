/**
 * @file createProxyModule.tsx
 * @description @akalin/proxy_module - Modül Fabrikası.
 * @akalin/module_core (`IModuleDefinition` ve `ModuleRegistry`) ile %100 uyumlu
 * Bağlantı Havuzu, Dinamik Tarayıcı Oturumları (Auto-Scale) ve Proxy Havuzu modülü üretir.
 */

import React, { lazy } from 'react';
import { Globe, MonitorCheck, ServerCog } from 'lucide-react';
import type { IModuleDefinition } from '@akalin/module_core';
import { CreateProxyModuleOptions, NodesPoolViewProps } from './types';
import {
  createRestProxyAdapter,
  ProxyModuleProvider,
  setGlobalProxyModuleConfig,
} from './adapters/ProxyServiceContext';
import { NodesPoolView } from './pages/NodesPoolPage';
import { NodesPoolPageSettingsForExternal } from './pages/NodesPoolPageSettingsForExternal';

const LazyNodesPoolPage = lazy(() => import('./pages/NodesPoolPage'));

export function createProxyModule(
  options?: CreateProxyModuleOptions
): IModuleDefinition {
  const id = options?.id || 'proxy-module';
  const appName = options?.appName || 'ThinkPort API';
  const baseRoute = (options?.baseRoute || '/nodes').replace(/\/$/, '');
  const settingsModuleId = options?.settingsModuleId || 'proxies';
  const maxConcurrentBrowsers = options?.maxConcurrentBrowsers ?? 16;

  const adapter =
    options?.adapter ||
    createRestProxyAdapter({
      baseUrl: '/admin/proxies',
      stateUrl: '/admin/state',
    });

  setGlobalProxyModuleConfig({
    adapter,
    appName,
    baseRoute,
    maxConcurrentBrowsers,
    onNotify: options?.onNotify,
  });

  const ConnectedNodesPoolPage: React.FC<NodesPoolViewProps> & {
    hasExternalSettings?: boolean;
  } = (props) => (
    <ProxyModuleProvider
      adapter={adapter}
      appName={appName}
      baseRoute={baseRoute}
      maxConcurrentBrowsers={
        props.maxConcurrentBrowsers ?? maxConcurrentBrowsers
      }
      onNotify={
        props.onShowToast
          ? (msg) => props.onShowToast?.(msg)
          : options?.onNotify
      }
    >
      <NodesPoolView {...props} />
    </ProxyModuleProvider>
  );
  ConnectedNodesPoolPage.hasExternalSettings = true;

  const ConnectedLazyDashboardRoute: React.FC<NodesPoolViewProps> = (props) => (
    <ProxyModuleProvider
      adapter={adapter}
      appName={appName}
      baseRoute={baseRoute}
      maxConcurrentBrowsers={maxConcurrentBrowsers}
      onNotify={options?.onNotify}
    >
      <LazyNodesPoolPage activeSection="dashboard" {...props} />
    </ProxyModuleProvider>
  );

  const ConnectedLazySessionsRoute: React.FC<NodesPoolViewProps> = (props) => (
    <ProxyModuleProvider
      adapter={adapter}
      appName={appName}
      baseRoute={baseRoute}
      maxConcurrentBrowsers={maxConcurrentBrowsers}
      onNotify={options?.onNotify}
    >
      <LazyNodesPoolPage activeSection="sessions" {...props} />
    </ProxyModuleProvider>
  );

  const ConnectedLazyProxiesRoute: React.FC<NodesPoolViewProps> = (props) => (
    <ProxyModuleProvider
      adapter={adapter}
      appName={appName}
      baseRoute={baseRoute}
      maxConcurrentBrowsers={maxConcurrentBrowsers}
      onNotify={options?.onNotify}
    >
      <LazyNodesPoolPage activeSection="proxies" {...props} />
    </ProxyModuleProvider>
  );

  return {
    id,
    aliases: ['proxy', 'proxies', 'nodes', 'proxy_module', 'baglanti_havuzu'],
    title: 'Bağlantı & Proxy Havuzu Yönetimi',
    name: 'Bağlantı & Proxy Havuzu Yönetimi',
    description:
      'Anti-Bot IP rotasyon proxy havuzu, canlı ücretsiz proxy keşfi, TCP ping/gecikme sağlık denetimi ve dinamik tarayıcı oturum (Auto-Scale) yönetimi modülü.',
    version: '1.0.0',
    permissionPrefix: 'proxy',
    icon: <Globe size={20} />,
    iconName: 'Globe',
    order: options?.order ?? 50,
    isCore: true,
    defaultActive: true,

    routes: [
      {
        path: baseRoute,
        element: <ConnectedLazyDashboardRoute />,
        title: 'Bağlantı Havuzu — Dashboard',
        requiredPermissions: ['proxy.view'],
      },
      {
        path: `${baseRoute}/proxies`,
        element: <ConnectedLazyProxiesRoute />,
        title: 'Bağlantı Havuzu — Proxy Listesi',
        requiredPermissions: ['proxy.view'],
      },
    ],

    menuItems: [
      {
        id: 'proxy-module-root',
        label: 'Bağlantı Havuzu',
        icon: <Globe size={20} />,
        order: options?.order ?? 50,
        isDropdown: true,
        children: [
          {
            id: 'proxy-pool-dashboard',
            label: 'Dashboard',
            path: baseRoute,
            icon: <ServerCog size={18} />,
            requiredPermissions: ['proxy.view'],
          },
          {
            id: 'proxy-pool-list',
            label: 'Proxy Listesi',
            path: `${baseRoute}/proxies`,
            icon: <Globe size={18} />,
            requiredPermissions: ['proxy.view'],
          },
        ],
      },
    ],

    settingsModules: [
      {
        id: settingsModuleId,
        name:
          options?.settingsModuleName || 'Bağlantı & Proxy Havuzu Ayarları',
        desc:
          options?.settingsModuleDesc ||
          'Anti-Bot proxy düğümleri, ücretsiz proxy çekimi, gecikme testleri ve dinamik tarayıcı oturum havuzu yapılandırması',
        icon: <Globe size={22} />,
        badge: options?.settingsModuleBadge || 'Proxy & Auto-Scale',
        keywords:
          'proxy socks5 socks4 http https havuz ip rotasyon gecikme ping oturum tarayıcı autoscale',
        order: options?.settingsOrder ?? 50,
        hasOwnLayout: true,
        aliases: ['ProxyAyarlari', 'proxies', 'nodes'],
        component: ConnectedLazyProxiesRoute,
      },
    ],

    lists: [
      {
        id: 'proxy-dugumleri-liste',
        category: 'liste',
        titleKey: 'menu_proxy_dugumleri_liste',
        title: 'Proxy Düğümleri Listesi',
        description:
          'HTTP, HTTPS, SOCKS4 ve SOCKS5 proxy düğümleri, ülke/veri merkezi dağılımı ve gecikme durum listesi.',
        route: `${baseRoute}/proxies`,
        listRoute: `${baseRoute}/proxies`,
        hasExternalSettings: true,
        externalSettingsComponent: NodesPoolPageSettingsForExternal,
        customActions: [
          {
            action: 'fetch_free_proxies',
            labelKey: 'Canlı Ücretsiz Proxy Çekme',
            description:
              'Açık kaynaklı proxy sağlayıcılarından canlı SOCKS5/HTTP proxy düğümleri çeker.',
          },
          {
            action: 'check_all_latency',
            labelKey: 'Toplu TCP Ping & Gecikme Testi',
            description:
              'Havuzdaki tüm proxy düğümlerinin bağlantı gecikmesini test eder.',
          },
        ],
      },
      {
        id: 'tarayici-oturumlari-liste',
        category: 'liste',
        titleKey: 'menu_tarayici_oturumlari_liste',
        title: 'Tarayıcı Oturumları Listesi',
        description:
          'Sabit (Warm) ve Dinamik (Auto-Scale) tarayıcı oturumları listesi.',
        route: `${baseRoute}/sessions`,
        listRoute: `${baseRoute}/sessions`,
        hasExternalSettings: true,
        externalSettingsComponent: NodesPoolPageSettingsForExternal,
      },
    ],

    cards: [
      {
        id: 'proxy-dugum-karti',
        category: 'kart',
        titleKey: 'Proxy Düğüm Kartı',
        title: 'Proxy Düğüm Kartı',
        route: `${baseRoute}/proxies`,
        hasExternalSettings: true,
        externalSettingsComponent: NodesPoolPageSettingsForExternal,
      },
    ],

    operations: [
      {
        id: 'proxy-havuz-yonetimi',
        category: 'islem',
        titleKey: 'Proxy Havuzu ve Dinamik Oturum Operasyonları',
        useStandardCrud: true,
        customActions: [
          {
            action: 'goruntule',
            labelKey: 'Proxy Havuzunu Görüntüleme',
            description:
              'Proxy düğümlerini, oturumları ve telemetri panosunu görüntüleme yetkisi.',
          },
          {
            action: 'ücretsiz-cek',
            labelKey: 'Ücretsiz Proxy Çekme',
            description:
              'Açık kaynaklardan havuza otomatik ücretsiz proxy çekme yetkisi.',
          },
          {
            action: 'ping-test',
            labelKey: 'Ping ve Sağlık Kontrolü',
            description: 'Proxy düğümlerinde TCP gecikme testi başlatma yetkisi.',
          },
          {
            action: 'oturum-baslat',
            labelKey: 'Dinamik Oturum Başlatma / Sonlandırma',
            description:
              'Auto-Scale tarayıcı oturumu başlatma ve boştaki oturumları temizleme yetkisi.',
          },
        ],
      },
    ],

    permissions: [
      {
        key: 'proxy.view',
        name: 'Proxy Havuzunu Görüntüleme',
        description:
          'Proxy listesini ve bağlantı havuzu telemetrisini görüntüleme yetkisi.',
        group: 'Bağlantı & Proxy Havuzu',
      },
      {
        key: 'proxy.manage',
        name: 'Proxy Düğümlerini Yönetme',
        description:
          'Tekil/toplu proxy ekleme, ücretsiz proxy çekme, durum değiştirme ve silme yetkisi.',
        group: 'Bağlantı & Proxy Havuzu',
      },
      {
        key: 'proxy.sessions.manage',
        name: 'Dinamik Tarayıcı Oturumlarını Yönetme',
        description:
          'Dinamik tarayıcı oturumu başlatma, temizleme (Scale-Down) ve sonlandırma yetkisi.',
        group: 'Bağlantı & Proxy Havuzu',
      },
    ],

    components: {
      NodesPoolView: ConnectedNodesPoolPage,
      NodesPoolPage: ConnectedNodesPoolPage,
      NodesPoolPageSettingsForExternal,
    },
  };
}

export const ProxyModulu = createProxyModule();
export const ProxyManagementModule = ProxyModulu;
export default ProxyModulu;
