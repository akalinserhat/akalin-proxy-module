/**
 * @file NodesPoolPage.tsx
 * @description @akalin/proxy_module - Bağlantı Havuzu, Dinamik Tarayıcı Oturumları (Auto-Scale)
 * ve Anti-Bot Proxy Havuzu Yönetim Ekranı.
 * Hem kontrollü (props ile) hem de otonom (ProxyModuleContext adaptörü ile) modda çalışır.
 */

import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import {
  Activity,
  CloudDownload,
  Globe,
  MonitorCheck,
  Plus,
  RefreshCw,
  Server,
  ServerCog,
  ShieldCheck,
  Trash2,
  Wifi,
  Zap,
} from 'lucide-react';
import {
  BaseButton,
  BaseDropdownSecici,
  BaseInput,
  BasePage,
  BasePopup,
  BaseSystemCard,
  DashboardActivityFeedView,
  DashboardDistributionView,
  DashboardStatCard,
  DashboardTimelineChartView,
  FieldError,
  NotInput,
  TabLayout,
  TamsayiInput,
  useAlertDialog,
  type DashboardActivityEvent,
  type DashboardDistributionItem,
  type DropdownOption,
} from '@akalin/ui';
import {
  useGlobalSearch,
  useSearchFieldsRegister,
  type SearchType,
} from '@akalin/global_search_module';
import {
  BrowserSessionDTO,
  CreateBrowserSessionRequestDTO,
  NodesPoolSection,
  NodesPoolViewProps,
  PoolDashboardMetricsDTO,
  PoolScalingEventDTO,
  ProxyNodeDTO,
} from '../types';
import { useProxyModule } from '../adapters/ProxyServiceContext';
import {
  buildDefaultPoolTimeline,
  DEFAULT_SEED_PROXIES,
  DEFAULT_SEED_SESSIONS,
  getBulkProxyDefaultValues,
  getSingleProxyDefaultValues,
  getSpawnSessionDefaultValues,
  PROXY_COUNTRY_OPTIONS,
  PROXY_PROTOCOL_OPTIONS,
  SPAWN_PROVIDER_OPTIONS,
} from '../defaults/proxyDefaultValue';
import {
  validateBulkProxyField,
  validateBulkProxyForm,
  validateSingleProxyField,
  validateSingleProxyForm,
  validateSpawnSessionField,
  validateSpawnSessionForm,
} from '../validators/proxyValidation';
import { useProxyAutoFocus } from '../hooks/useProxyAutoFocus';
import { useProxyTranslation } from '../i18n/proxyTranslations';

function resolveProtocolFilterParam(selectedIds: string[]): string {
  if (selectedIds.includes('proto:socks5')) return 'socks5';
  if (selectedIds.includes('proto:socks4')) return 'socks4';
  if (selectedIds.includes('proto:http')) return 'http';
  return 'all';
}

export type NodesPoolPageComponent = React.FC<NodesPoolViewProps> & {
  hasExternalSettings?: boolean;
};

export const NodesPoolView: NodesPoolPageComponent = ({
  activeSection: propActiveSection,
  sessions: propSessions,
  proxies: propProxies,
  poolDashboard,
  maxConcurrentBrowsers: propMaxConcurrentBrowsers,
  onNavigateSection,
  onToggleProxy,
  onSpawnDynamicSession,
  onPruneDynamicSessions,
  onTerminateSession,
  onRefreshState,
  onShowToast,
}) => {
  const { t } = useProxyTranslation();
  const { showAlert } = useAlertDialog();
  const {
    adapter,
    maxConcurrentBrowsers: ctxMaxConcurrent,
    onNotify,
  } = useProxyModule();
  const { state: globalSearchState, activeSearchType, selectedFilterTypes } =
    useGlobalSearch();

  const maxConcurrentBrowsers =
    propMaxConcurrentBrowsers ?? ctxMaxConcurrent ?? 16;

  const [localSection, setLocalSection] = useState<NodesPoolSection>(
    propActiveSection || 'dashboard'
  );
  useEffect(() => {
    if (propActiveSection) {
      setLocalSection(propActiveSection);
    }
  }, [propActiveSection]);

  const activeSection = propActiveSection ?? localSection;

  const [internalProxies, setInternalProxies] =
    useState<ProxyNodeDTO[]>(DEFAULT_SEED_PROXIES);
  const [internalSessions, setInternalSessions] =
    useState<BrowserSessionDTO[]>(DEFAULT_SEED_SESSIONS);

  const proxies = propProxies ?? internalProxies;
  const sessions = propSessions ?? internalSessions;

  const notify = useCallback(
    (msg: string, type: 'success' | 'error' | 'info' = 'success') => {
      if (onShowToast) {
        onShowToast(msg);
      } else if (onNotify) {
        onNotify(msg, type);
      }
    },
    [onShowToast, onNotify]
  );

  const loadAutonomousData = useCallback(async () => {
    if (propProxies && propSessions) return;
    try {
      const [fetchedProxies, fetchedSessions] = await Promise.all([
        propProxies ? Promise.resolve(propProxies) : adapter.getProxies(),
        propSessions ? Promise.resolve(propSessions) : adapter.getSessions(),
      ]);
      if (!propProxies && Array.isArray(fetchedProxies)) {
        setInternalProxies(fetchedProxies);
      }
      if (!propSessions && Array.isArray(fetchedSessions)) {
        setInternalSessions(fetchedSessions);
      }
    } catch {
      // Keep seed fallback
    }
  }, [adapter, propProxies, propSessions]);

  useEffect(() => {
    loadAutonomousData();
  }, [loadAutonomousData]);

  const refreshAll = useCallback(async () => {
    if (onRefreshState) {
      await onRefreshState();
    } else {
      await loadAutonomousData();
    }
  }, [onRefreshState, loadAutonomousData]);

  const handleNavigateSection = useCallback(
    (sub: NodesPoolSection) => {
      if (onNavigateSection) {
        onNavigateSection(sub);
      } else {
        setLocalSection(sub);
      }
    },
    [onNavigateSection]
  );

  const [isFetchingFree, setIsFetchingFree] = useState(false);
  const [isCheckingAll, setIsCheckingAll] = useState(false);
  const [checkingProxyId, setCheckingProxyId] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTabId, setModalTabId] = useState<number>(1);
  const [submitting, setSubmitting] = useState(false);

  const [isSpawnModalOpen, setIsSpawnModalOpen] = useState(false);
  const [spawningSession, setSpawningSession] = useState(false);
  const [pruningSessions, setPruningSessions] = useState(false);

  const [singleForm, setSingleForm] = useState(getSingleProxyDefaultValues);
  const [bulkForm, setBulkForm] = useState(getBulkProxyDefaultValues);
  const [spawnForm, setSpawnForm] = useState(getSpawnSessionDefaultValues);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const proxyModalContainerRef = useRef<HTMLDivElement | null>(null);
  const spawnModalContainerRef = useRef<HTMLDivElement | null>(null);

  useProxyAutoFocus(proxyModalContainerRef, [isModalOpen, modalTabId]);
  useProxyAutoFocus(spawnModalContainerRef, [isSpawnModalOpen]);

  const clearFieldError = useCallback((field: string) => {
    setFormErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }, []);

  const proxyTypeOptions = useMemo<DropdownOption[]>(
    () => [
      { id: 'residential', value: 'residential', label: t('nodes.typeResidential') },
      { id: 'mobile', value: 'mobile', label: t('nodes.typeMobile') },
      { id: 'isp', value: 'isp', label: t('nodes.typeIsp') },
      { id: 'datacenter', value: 'datacenter', label: t('nodes.typeDatacenter') },
    ],
    [t]
  );

  const spawnProxyOptions = useMemo<DropdownOption[]>(
    () => [
      {
        id: '',
        value: '',
        label: t('nodes.spawnAutoProxyOption'),
      },
      ...proxies
        .filter((p) => p.status === 'active')
        .map((p) => ({
          id: p.id,
          value: p.id,
          label: `${p.endpoint} (${p.country} · ${p.protocol.toUpperCase()} · ${p.latency_ms ?? 45} ms)`,
        })),
    ],
    [proxies, t]
  );

  const warmSessionCount = useMemo(
    () => sessions.filter((s) => !s.is_dynamic).length,
    [sessions]
  );

  const dynamicSessionCount = useMemo(
    () => sessions.filter((s) => Boolean(s.is_dynamic)).length,
    [sessions]
  );

  const idleDynamicCount = useMemo(
    () =>
      sessions.filter((s) => Boolean(s.is_dynamic) && s.status === 'idle').length,
    [sessions]
  );

  const nodesSearchFields = useMemo<SearchType[]>(() => {
    if (activeSection === 'sessions') {
      return [
        {
          id: 'Tumu',
          label: t('nodes.searchGeneral'),
          iconName: 'Search',
          type: 'text',
          placeholder: t('nodes.searchSessionsPlaceholder'),
        },
        {
          id: 'provider',
          label: t('nodes.searchProviderLabel'),
          iconName: 'Cloud',
          type: 'text',
          placeholder: t('nodes.searchProviderPlaceholder'),
        },
        {
          id: 'account',
          label: t('nodes.searchAccountLabel'),
          iconName: 'Users',
          type: 'text',
          placeholder: t('nodes.searchAccountPlaceholder'),
        },
        {
          id: 'proxy',
          label: t('nodes.searchAssignedProxyLabel'),
          iconName: 'Layers',
          type: 'text',
          placeholder: t('nodes.searchAssignedProxyPlaceholder'),
        },
        {
          id: 'session_mode',
          label: t('nodes.searchSessionModeLabel'),
          iconName: 'Filter',
          type: 'enum',
          isEnum: true,
          category: 'filter',
          options: [
            { id: 'mode:warm', label: t('nodes.modeWarm') },
            { id: 'mode:dynamic', label: t('nodes.modeDynamic') },
          ],
        },
        {
          id: 'session_status',
          label: t('nodes.searchSessionStatusLabel'),
          iconName: 'CheckCircle',
          type: 'enum',
          isEnum: true,
          category: 'filter',
          options: [
            { id: 'status:idle', label: t('status.idle') },
            { id: 'status:busy', label: t('status.busy') },
          ],
        },
      ];
    }

    return [
      {
        id: 'Tumu',
        label: t('nodes.searchGeneral'),
        iconName: 'Search',
        type: 'text',
        placeholder: t('nodes.searchPlaceholder'),
      },
      {
        id: 'endpoint',
        label: t('nodes.searchEndpointLabel'),
        iconName: 'Hash',
        type: 'text',
        placeholder: t('nodes.searchEndpointPlaceholder'),
      },
      {
        id: 'country',
        label: t('nodes.searchCountryLabel'),
        iconName: 'MapPin',
        type: 'text',
        placeholder: t('nodes.searchCountryPlaceholder'),
      },
      {
        id: 'provider',
        label: t('nodes.searchProviderLabel'),
        iconName: 'Building2',
        type: 'text',
        placeholder: t('nodes.searchNodeProviderPlaceholder'),
      },
      {
        id: 'protocol_filter',
        label: t('nodes.fieldProtocol'),
        iconName: 'Filter',
        type: 'enum',
        isEnum: true,
        category: 'filter',
        options: [
          { id: 'proto:http', label: t('nodes.filterHttp') },
          { id: 'proto:socks5', label: t('nodes.filterSocks5') },
          { id: 'proto:socks4', label: t('nodes.filterSocks4') },
        ],
      },
      {
        id: 'proxy_type_filter',
        label: t('nodes.fieldType'),
        iconName: 'Layers',
        type: 'enum',
        isEnum: true,
        category: 'filter',
        options: [
          { id: 'type:residential', label: t('nodes.typeResidential') },
          { id: 'type:mobile', label: t('nodes.typeMobile') },
          { id: 'type:isp', label: t('nodes.typeIsp') },
          { id: 'type:datacenter', label: t('nodes.typeDatacenter') },
        ],
      },
      {
        id: 'proxy_status_filter',
        label: t('nodes.searchNodeStatusLabel'),
        iconName: 'CheckCircle',
        type: 'enum',
        isEnum: true,
        category: 'filter',
        options: [
          { id: 'status:active', label: t('status.active') },
          { id: 'status:cooldown', label: t('status.cooldown') },
        ],
      },
    ];
  }, [activeSection, t]);

  useSearchFieldsRegister(nodesSearchFields);

  const filteredSessions = useMemo(() => {
    const q = (globalSearchState.searchTerm || '').trim().toLowerCase();
    const activeField = activeSearchType?.id || 'Tumu';
    const selectedIds = selectedFilterTypes.map((f) => f.id);
    const modeFilters = selectedIds.filter((id) => id.startsWith('mode:'));
    const statusFilters = selectedIds.filter((id) => id.startsWith('status:'));

    return sessions.filter((s) => {
      if (modeFilters.length > 0) {
        const isDyn = Boolean(s.is_dynamic);
        const matchMode =
          (modeFilters.includes('mode:dynamic') && isDyn) ||
          (modeFilters.includes('mode:warm') && !isDyn);
        if (!matchMode) return false;
      }
      if (statusFilters.length > 0) {
        const isIdle = s.status === 'idle';
        const matchStatus =
          (statusFilters.includes('status:idle') && isIdle) ||
          (statusFilters.includes('status:busy') && !isIdle);
        if (!matchStatus) return false;
      }
      if (!q) return true;
      if (activeField === 'provider') {
        return (s.provider || '').toLowerCase().includes(q);
      }
      if (activeField === 'account') {
        return (s.account || '').toLowerCase().includes(q);
      }
      if (activeField === 'proxy') {
        return (s.proxy || '').toLowerCase().includes(q);
      }
      return (
        (s.id || '').toLowerCase().includes(q) ||
        (s.provider || '').toLowerCase().includes(q) ||
        (s.account || '').toLowerCase().includes(q) ||
        (s.proxy || '').toLowerCase().includes(q)
      );
    });
  }, [
    sessions,
    globalSearchState.searchTerm,
    activeSearchType,
    selectedFilterTypes,
  ]);

  const filteredProxies = useMemo(() => {
    const q = (globalSearchState.searchTerm || '').trim().toLowerCase();
    const activeField = activeSearchType?.id || 'Tumu';
    const selectedIds = selectedFilterTypes.map((f) => f.id);
    const protoFilters = selectedIds.filter((id) => id.startsWith('proto:'));
    const typeFilters = selectedIds.filter((id) => id.startsWith('type:'));
    const statusFilters = selectedIds.filter((id) => id.startsWith('status:'));

    return proxies.filter((p) => {
      const proto = (p.protocol || '').toLowerCase();
      const ptype = (p.proxy_type || 'residential').toLowerCase();

      if (protoFilters.length > 0) {
        const matchProto =
          (protoFilters.includes('proto:http') &&
            (proto === 'http' || proto === 'https')) ||
          (protoFilters.includes('proto:socks5') && proto === 'socks5') ||
          (protoFilters.includes('proto:socks4') && proto === 'socks4');
        if (!matchProto) return false;
      }

      if (typeFilters.length > 0) {
        if (!typeFilters.includes(`type:${ptype}`)) return false;
      }

      if (statusFilters.length > 0) {
        const isActive = p.status === 'active';
        const matchStatus =
          (statusFilters.includes('status:active') && isActive) ||
          (statusFilters.includes('status:cooldown') && !isActive);
        if (!matchStatus) return false;
      }

      if (!q) return true;
      if (activeField === 'endpoint') {
        return p.endpoint.toLowerCase().includes(q);
      }
      if (activeField === 'country') {
        return (
          p.country.toLowerCase().includes(q) ||
          (p.city || '').toLowerCase().includes(q)
        );
      }
      if (activeField === 'provider') {
        return (p.provider || '').toLowerCase().includes(q);
      }

      return (
        p.endpoint.toLowerCase().includes(q) ||
        p.country.toLowerCase().includes(q) ||
        (p.city || '').toLowerCase().includes(q) ||
        (p.provider || '').toLowerCase().includes(q) ||
        proto.includes(q)
      );
    });
  }, [
    proxies,
    globalSearchState.searchTerm,
    activeSearchType,
    selectedFilterTypes,
  ]);

  const activeCount = useMemo(
    () => proxies.filter((p) => p.status === 'active').length,
    [proxies]
  );

  const avgLatency = useMemo(() => {
    const withLatency = proxies.filter((p) => typeof p.latency_ms === 'number');
    if (withLatency.length === 0) return 48;
    const sum = withLatency.reduce((acc, p) => acc + (p.latency_ms || 50), 0);
    return Math.round(sum / withLatency.length);
  }, [proxies]);

  const getProxyTypeLabel = useCallback(
    (type?: string) => {
      switch ((type || 'residential').toLowerCase()) {
        case 'mobile':
          return t('nodes.typeMobile');
        case 'isp':
          return t('nodes.typeIsp');
        case 'datacenter':
          return t('nodes.typeDatacenter');
        default:
          return t('nodes.typeResidential');
      }
    },
    [t]
  );

  const handleFetchFreeProxies = async () => {
    setIsFetchingFree(true);
    try {
      const selectedIds = selectedFilterTypes.map((f) => f.id);
      const data = await adapter.fetchFreeProxies({
        protocol: resolveProtocolFilterParam(selectedIds),
        limit: 6,
      });
      notify(t('nodes.proxyFetchedToast', { count: data.added_count || 6 }));
      await refreshAll();
    } finally {
      setIsFetchingFree(false);
    }
  };

  const handleCheckAllProxies = async () => {
    setIsCheckingAll(true);
    try {
      await adapter.checkAllProxies();
      notify(t('nodes.proxyCheckedToast'));
      await refreshAll();
    } finally {
      setIsCheckingAll(false);
    }
  };

  const handleCheckSingleProxy = async (proxyId: string) => {
    setCheckingProxyId(proxyId);
    try {
      await adapter.checkSingleProxy(proxyId);
      notify(t('nodes.proxyCheckedToast'));
      await refreshAll();
    } finally {
      setCheckingProxyId(null);
    }
  };

  const handleToggleSingleProxy = async (proxyId: string) => {
    if (onToggleProxy) {
      await onToggleProxy(proxyId);
    } else {
      await adapter.toggleProxyStatus(proxyId);
      notify(t('nodes.proxyUpdatedToast'));
      await refreshAll();
    }
  };

  const handleDeleteProxy = (proxy: ProxyNodeDTO) => {
    const doDelete = async () => {
      await adapter.deleteProxy(proxy.id);
      notify(t('nodes.proxyDeletedToast'));
      await refreshAll();
    };
    showAlert(
      'confirm',
      t('nodes.deleteProxy'),
      t('nodes.deleteProxyConfirm', {
        endpoint: proxy.endpoint,
        country: proxy.country,
      }),
      doDelete
    );
  };

  const handleSaveModal = async () => {
    if (modalTabId === 1) {
      const errors = validateSingleProxyForm(singleForm, t);
      if (Object.keys(errors).length > 0) {
        setFormErrors(errors);
        return;
      }
    } else {
      const errors = validateBulkProxyForm(bulkForm, t);
      if (Object.keys(errors).length > 0) {
        setFormErrors(errors);
        return;
      }
    }

    setSubmitting(true);
    try {
      if (modalTabId === 1) {
        await adapter.createProxy({
          protocol: singleForm.protocol,
          endpoint: singleForm.endpoint.trim(),
          country: singleForm.country.trim() || 'TR',
          city: singleForm.city.trim() || 'Istanbul',
          proxy_type: singleForm.proxyType,
          provider: singleForm.provider.trim() || 'Custom Node',
        });
        setSingleForm(getSingleProxyDefaultValues());
        setFormErrors({});
        setIsModalOpen(false);
        notify(t('nodes.proxyAddedToast'));
        await refreshAll();
      } else {
        const data = await adapter.bulkImport({
          raw_list: bulkForm.bulkList,
          default_protocol: bulkForm.bulkProtocol,
          default_country: bulkForm.bulkCountry,
          default_type: bulkForm.bulkType,
          default_provider: 'Bulk Pool',
        });
        setBulkForm(getBulkProxyDefaultValues());
        setFormErrors({});
        setIsModalOpen(false);
        notify(t('nodes.proxyBulkToast', { count: data.added_count || 0 }));
        await refreshAll();
      }
    } finally {
      setSubmitting(false);
    }
  };

  const [sqliteTelemetry, setSqliteTelemetry] = useState<{
    timeline: PoolDashboardMetricsDTO['timeline'];
    recent_events: PoolScalingEventDTO[];
  } | null>(null);

  const loadSqlitePoolDashboard = useCallback(async () => {
    try {
      const data = await adapter.getDashboardMetrics();
      const events = data?.recent_events || data?.scaling_events || [];
      if (data && (data.timeline?.length || events.length)) {
        setSqliteTelemetry({
          timeline: data.timeline || [],
          recent_events: events,
        });
      }
    } catch {
      // Fallback to prop or computed defaults
    }
  }, [adapter]);

  useEffect(() => {
    loadSqlitePoolDashboard();
  }, [loadSqlitePoolDashboard]);

  const busySessionCount = useMemo(
    () => sessions.filter((s) => s.status !== 'idle').length,
    [sessions]
  );

  const totalRequestsServed = useMemo(
    () => sessions.reduce((acc, s) => acc + (s.requests_served || 0), 0),
    [sessions]
  );

  const utilizationPct = useMemo(
    () =>
      Math.round((sessions.length / Math.max(1, maxConcurrentBrowsers)) * 100),
    [sessions.length, maxConcurrentBrowsers]
  );

  const handleSpawnSessionModal = async () => {
    const errors = validateSpawnSessionForm(spawnForm, t);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setSpawningSession(true);
    try {
      const ttlNum = Math.max(30, Number(spawnForm.spawnIdleTtl) || 300);
      const reqPayload: CreateBrowserSessionRequestDTO = {
        provider: spawnForm.spawnProvider,
        account: spawnForm.spawnAccount.trim() || undefined,
        proxy_id: spawnForm.spawnProxyId || undefined,
        idle_ttl_sec: ttlNum,
      };

      if (onSpawnDynamicSession) {
        await onSpawnDynamicSession(reqPayload);
      } else {
        const created = await adapter.spawnDynamicSession(reqPayload);
        notify(t('nodes.sessionSpawnedToast', { id: created.id }));
        await refreshAll();
      }

      try {
        const nextTotal = sessions.length + 1;
        const nextDynamic = dynamicSessionCount + 1;
        const updated = await adapter.recordPoolEvent({
          event_type: 'scale_up',
          provider: spawnForm.spawnProvider,
          proxy_id: spawnForm.spawnProxyId || proxies[0]?.id || 'px-01',
          reason: `${spawnForm.spawnProvider} (TTL: ${ttlNum}s)`,
          total_sessions_after: nextTotal,
          dynamic_sessions_after: nextDynamic,
          warm_sessions_after: warmSessionCount,
          busy_sessions_after: busySessionCount,
          max_capacity: maxConcurrentBrowsers,
          active_proxies: activeCount,
          cooldown_proxies: proxies.length - activeCount,
          avg_proxy_latency_ms: avgLatency,
        });
        if (updated?.timeline) {
          setSqliteTelemetry({
            timeline: updated.timeline,
            recent_events: updated.recent_events || updated.scaling_events || [],
          });
        }
      } catch {
        // Ignore bridge error
      }
      setSpawnForm(getSpawnSessionDefaultValues());
      setFormErrors({});
      setIsSpawnModalOpen(false);
    } finally {
      setSpawningSession(false);
    }
  };

  const handlePruneDynamic = async () => {
    setPruningSessions(true);
    try {
      const prunedCount = idleDynamicCount;
      if (onPruneDynamicSessions) {
        await onPruneDynamicSessions();
      } else {
        const res = await adapter.pruneIdleDynamicSessions();
        notify(t('nodes.sessionsPrunedToast', { count: res.removed_count }));
        await refreshAll();
      }
      try {
        const nextTotal = Math.max(
          warmSessionCount,
          sessions.length - prunedCount
        );
        const nextDynamic = Math.max(0, dynamicSessionCount - prunedCount);
        const updated = await adapter.recordPoolEvent({
          event_type: 'scale_down',
          provider: 'pool-gc',
          reason: `Scale-Down (${prunedCount})`,
          total_sessions_after: nextTotal,
          dynamic_sessions_after: nextDynamic,
          warm_sessions_after: warmSessionCount,
          busy_sessions_after: busySessionCount,
          max_capacity: maxConcurrentBrowsers,
          active_proxies: activeCount,
          cooldown_proxies: proxies.length - activeCount,
          avg_proxy_latency_ms: avgLatency,
        });
        if (updated?.timeline) {
          setSqliteTelemetry({
            timeline: updated.timeline,
            recent_events: updated.recent_events || updated.scaling_events || [],
          });
        }
      } catch {
        // Ignore bridge error
      }
    } finally {
      setPruningSessions(false);
    }
  };

  const handleConfirmTerminateSession = (session: BrowserSessionDTO) => {
    showAlert(
      'confirm',
      t('nodes.terminateSessionTitle'),
      t('nodes.terminateSessionConfirm', {
        id: session.id,
        provider: session.provider,
      }),
      async () => {
        if (onTerminateSession) {
          await onTerminateSession(session.id);
        } else {
          await adapter.terminateSession(session.id);
          notify(t('nodes.sessionTerminatedToast', { id: session.id }));
          await refreshAll();
        }
        try {
          const nextTotal = Math.max(0, sessions.length - 1);
          const nextDynamic = session.is_dynamic
            ? Math.max(0, dynamicSessionCount - 1)
            : dynamicSessionCount;
          const nextWarm = !session.is_dynamic
            ? Math.max(0, warmSessionCount - 1)
            : warmSessionCount;
          const updated = await adapter.recordPoolEvent({
            event_type: 'scale_down',
            provider: session.provider,
            session_id: session.id,
            proxy_id: session.proxy,
            reason: `${session.id} (${session.provider})`,
            total_sessions_after: nextTotal,
            dynamic_sessions_after: nextDynamic,
            warm_sessions_after: nextWarm,
            busy_sessions_after: busySessionCount,
            max_capacity: maxConcurrentBrowsers,
            active_proxies: activeCount,
            cooldown_proxies: proxies.length - activeCount,
            avg_proxy_latency_ms: avgLatency,
          });
          if (updated?.timeline) {
            setSqliteTelemetry({
              timeline: updated.timeline,
              recent_events:
                updated.recent_events || updated.scaling_events || [],
            });
          }
        } catch {
          // Ignore bridge error
        }
      }
    );
  };

  const isDashboardView = activeSection === 'dashboard';
  const isSessionsView = activeSection === 'sessions';
  const isProxiesView = activeSection === 'proxies';

  const timelinePoints = useMemo(() => {
    const baseTimeline = sqliteTelemetry?.timeline?.length
      ? sqliteTelemetry.timeline
      : poolDashboard?.timeline?.length
        ? poolDashboard.timeline
        : buildDefaultPoolTimeline(
            maxConcurrentBrowsers,
            activeCount,
            proxies.length
          );

    const livePoint = {
      id: 'live-now',
      time_label: t('nodes.nowLabel'),
      total_sessions: sessions.length,
      active_busy_sessions: busySessionCount,
      idle_sessions: Math.max(0, sessions.length - busySessionCount),
      warm_sessions: warmSessionCount,
      dynamic_sessions: dynamicSessionCount,
      max_capacity: maxConcurrentBrowsers,
      active_proxies: activeCount,
      cooldown_proxies: Math.max(0, proxies.length - activeCount),
      avg_proxy_latency_ms: avgLatency,
      requests_per_min: Math.max(
        12,
        busySessionCount * 7 + sessions.length * 2
      ),
      timestamp_iso: new Date().toISOString(),
    };

    return [...baseTimeline.slice(-11), livePoint];
  }, [
    sqliteTelemetry,
    poolDashboard,
    maxConcurrentBrowsers,
    activeCount,
    proxies.length,
    sessions.length,
    busySessionCount,
    warmSessionCount,
    dynamicSessionCount,
    avgLatency,
    t,
  ]);

  const providerDistributionItems = useMemo<DashboardDistributionItem[]>(() => {
    const providerColors: Record<
      string,
      'primary' | 'success' | 'warning' | 'danger' | 'info'
    > = {
      'chatgpt-web': 'success',
      'claude-web': 'warning',
      'deepseek-web': 'info',
      'gemini-web': 'primary',
      'pollinations-image': 'danger',
    };

    const grouped: Record<
      string,
      {
        total: number;
        busy: number;
        idle: number;
        warm: number;
        dynamic: number;
        requests: number;
      }
    > = {};

    sessions.forEach((s) => {
      const prov = s.provider || 'chatgpt-web';
      if (!grouped[prov]) {
        grouped[prov] = {
          total: 0,
          busy: 0,
          idle: 0,
          warm: 0,
          dynamic: 0,
          requests: 0,
        };
      }
      grouped[prov].total += 1;
      if (s.status === 'idle') {
        grouped[prov].idle += 1;
      } else {
        grouped[prov].busy += 1;
      }
      if (s.is_dynamic) {
        grouped[prov].dynamic += 1;
      } else {
        grouped[prov].warm += 1;
      }
      grouped[prov].requests += s.requests_served || 0;
    });

    const totalCount = Math.max(1, sessions.length);
    return Object.entries(grouped)
      .sort((a, b) => b[1].total - a[1].total)
      .map(([prov, stat]) => ({
        id: prov,
        label: prov,
        value: t('nodes.distProviderBadge', { count: stat.total }),
        percentage: Math.round((stat.total / totalCount) * 100),
        sublabel: `${stat.warm}S/${stat.dynamic}D · ${stat.busy}M`,
        color: providerColors[prov] || 'primary',
        badgeText: t('nodes.requestsServed', { count: stat.requests }),
      }));
  }, [sessions, t]);

  const proxyRegionDistributionItems = useMemo<
    DashboardDistributionItem[]
  >(() => {
    const regionColors: Array<
      'primary' | 'success' | 'info' | 'warning' | 'danger'
    > = ['primary', 'success', 'info', 'warning', 'danger'];
    const grouped: Record<
      string,
      {
        total: number;
        active: number;
        latencies: number[];
        cities: Set<string>;
      }
    > = {};

    proxies.forEach((p) => {
      const c = p.country || 'EU';
      if (!grouped[c]) {
        grouped[c] = { total: 0, active: 0, latencies: [], cities: new Set() };
      }
      grouped[c].total += 1;
      if (p.status === 'active') {
        grouped[c].active += 1;
      }
      if (typeof p.latency_ms === 'number') {
        grouped[c].latencies.push(p.latency_ms);
      }
      if (p.city) {
        grouped[c].cities.add(p.city);
      }
    });

    const totalProxies = Math.max(1, proxies.length);
    return Object.entries(grouped)
      .sort((a, b) => b[1].total - a[1].total)
      .map(([countryCode, info], idx) => {
        const avgLat = info.latencies.length
          ? Math.round(
              info.latencies.reduce((acc, v) => acc + v, 0) /
                info.latencies.length
            )
          : 55;
        const cityList = Array.from(info.cities).slice(0, 2).join(', ');
        return {
          id: countryCode,
          label: `${countryCode}${cityList ? ` (${cityList})` : ''}`,
          value: t('nodes.distActiveValue', {
            active: info.active,
            total: info.total,
          }),
          percentage: Math.round((info.total / totalProxies) * 100),
          sublabel:
            info.total - info.active > 0
              ? t('nodes.kpiCooldownCount', {
                  count: info.total - info.active,
                })
              : t('nodes.kpiAllActive'),
          color: regionColors[idx % regionColors.length],
          badgeText: `${avgLat} ms`,
        };
      });
  }, [proxies, t]);

  const activityFeedEvents = useMemo<DashboardActivityEvent[]>(() => {
    const rawEvents: PoolScalingEventDTO[] = sqliteTelemetry?.recent_events
      ?.length
      ? sqliteTelemetry.recent_events
      : poolDashboard?.recent_events || poolDashboard?.scaling_events || [];

    return rawEvents.map((ev: PoolScalingEventDTO) => {
      const isScaleUp =
        ev.event_type === 'scale_up' ||
        ev.event_type === 'autoscale_up' ||
        ev.event_type === 'manual_spawn';
      const isScaleDown =
        ev.event_type === 'scale_down' ||
        ev.event_type === 'autoscale_down' ||
        ev.event_type === 'session_terminated';
      const isProxyRotate =
        ev.event_type === 'proxy_rotate' || ev.event_type === 'proxy_cooldown';

      const variant: DashboardActivityEvent['variant'] = isScaleUp
        ? 'primary'
        : isScaleDown
          ? 'warning'
          : isProxyRotate
            ? 'info'
            : 'success';

      const badgeText = isScaleUp
        ? 'SCALE-UP'
        : isScaleDown
          ? 'SCALE-DOWN'
          : isProxyRotate
            ? 'PROXY-ROTATE'
            : 'HEALTH-CHECK';

      const title = isScaleUp
        ? t('nodes.eventScaleUpTitle', { provider: ev.provider })
        : isScaleDown
          ? t('nodes.eventScaleDownTitle', { provider: ev.provider })
          : isProxyRotate
            ? t('nodes.eventProxyRotateTitle', {
                target: ev.proxy_endpoint || ev.proxy_id || ev.provider,
              })
            : t('nodes.eventHealthCheckTitle', { provider: ev.provider });

      const rawTs = ev.created_at || ev.timestamp_iso || '';
      const tsLabel = rawTs
        ? rawTs.replace('T', ' ').slice(11, 19)
        : t('nodes.justNowLabel');
      const reasonText = ev.detail || ev.reason || '';

      return {
        id: ev.id,
        title,
        description: `${reasonText} · ${t('nodes.eventCapacityLabel')}: ${ev.total_sessions_after}/${maxConcurrentBrowsers}`,
        timestamp: tsLabel,
        variant,
        badgeText,
        icon: isScaleUp ? (
          <Zap size={14} />
        ) : isScaleDown ? (
          <Trash2 size={14} />
        ) : isProxyRotate ? (
          <RefreshCw size={14} />
        ) : (
          <ShieldCheck size={14} />
        ),
      };
    });
  }, [sqliteTelemetry, poolDashboard, maxConcurrentBrowsers, t]);

  return (
    <BasePage
      title={
        isDashboardView
          ? `${t('nav.nodes')} — ${t('nav.nodesDashboard')}`
          : isSessionsView
            ? `${t('nav.nodes')} — ${t('nav.nodesSessions')}`
            : `${t('nav.nodes')} — ${t('nav.nodesProxies')}`
      }
      subtitle={
        isDashboardView
          ? t('nodes.dashboardSubtitle')
          : isSessionsView
            ? t('nodes.sessionsSubtitle', {
                current: sessions.length,
                max: maxConcurrentBrowsers,
                warm: warmSessionCount,
                dynamic: dynamicSessionCount,
              })
            : `${t('nodes.activeNodesCount', { active: activeCount, total: proxies.length })} · ${t('nodes.avgLatency')}: ${avgLatency} ms`
      }
      icon={
        isDashboardView ? (
          <ServerCog size={22} />
        ) : isSessionsView ? (
          <MonitorCheck size={22} />
        ) : (
          <Globe size={22} />
        )
      }
      asForm={false}
      hideSaveButton={true}
      showBackButton={false}
      headerExtra={
        isDashboardView ? (
          <div className="flex items-center gap-8 flex-wrap">
            <BaseButton
              variant="outline"
              className="btn-sm"
              icon={<MonitorCheck size={15} />}
              text={t('nodes.sessionsCountBtn', { count: sessions.length })}
              onClick={() => handleNavigateSection('sessions')}
            />
            <BaseButton
              variant="outline"
              className="btn-sm"
              icon={<Globe size={15} />}
              text={t('nodes.proxiesCountBtn', { count: proxies.length })}
              onClick={() => handleNavigateSection('proxies')}
            />
            <BaseButton
              variant="primary"
              className="btn-sm"
              icon={<Zap size={15} />}
              text={t('nodes.spawnDynamicBtn')}
              onClick={() => {
                setFormErrors({});
                setIsSpawnModalOpen(true);
              }}
            />
          </div>
        ) : isSessionsView ? (
          <div className="flex items-center gap-8 flex-wrap">
            {idleDynamicCount > 0 && (
              <BaseButton
                variant="outline"
                className="btn-sm"
                icon={<Trash2 size={15} />}
                isSaving={pruningSessions}
                loadingText={t('nodes.pruningIdle')}
                text={t('nodes.pruneIdleBtn', { count: idleDynamicCount })}
                onClick={handlePruneDynamic}
              />
            )}
            <BaseButton
              variant="primary"
              className="btn-sm"
              icon={<Zap size={15} />}
              text={t('nodes.spawnDynamicBtn')}
              onClick={() => {
                setFormErrors({});
                setIsSpawnModalOpen(true);
              }}
            />
          </div>
        ) : (
          <div className="flex items-center gap-8 flex-wrap">
            <BaseButton
              variant="outline"
              className="btn-sm"
              icon={<Activity size={15} />}
              isSaving={isCheckingAll}
              loadingText={t('nodes.checkingAll')}
              text={t('nodes.checkAllBtn')}
              onClick={handleCheckAllProxies}
            />
            <BaseButton
              variant="outline"
              className="btn-sm"
              icon={<CloudDownload size={15} />}
              isSaving={isFetchingFree}
              loadingText={t('nodes.fetchingFree')}
              text={t('nodes.fetchFreeBtn')}
              onClick={handleFetchFreeProxies}
            />
            <BaseButton
              variant="primary"
              className="btn-sm"
              icon={<Plus size={15} />}
              text={t('nodes.addProxyBtn')}
              onClick={() => {
                setFormErrors({});
                setIsModalOpen(true);
              }}
            />
          </div>
        )
      }
    >
      <div className="flex-col gap-16">
        {isDashboardView && (
          <div className="flex-col gap-16">
            <div className="dashboard-grid-4">
              <DashboardStatCard
                title={t('nodes.kpiCapacityTitle')}
                value={`${sessions.length} / ${maxConcurrentBrowsers}`}
                subtitle={t('nodes.kpiCapacitySubtitle')}
                icon={<MonitorCheck size={18} />}
                variant="primary"
                badge={t('nodes.kpiCapacityBadge', { pct: utilizationPct })}
                progress={utilizationPct}
                secondaryLabel={t('nodes.kpiCapacitySecondaryLabel')}
                secondaryValue={t('nodes.kpiCapacitySecondaryValue', {
                  warm: warmSessionCount,
                  dynamic: dynamicSessionCount,
                })}
                onClick={() => handleNavigateSection('sessions')}
              />

              <DashboardStatCard
                title={t('nodes.kpiWorkloadTitle')}
                value={t('nodes.kpiWorkloadValue', {
                  busy: busySessionCount,
                  idle: Math.max(0, sessions.length - busySessionCount),
                })}
                subtitle={t('nodes.kpiWorkloadSubtitle')}
                icon={<Zap size={18} />}
                variant={busySessionCount > 0 ? 'warning' : 'success'}
                trend={{
                  value: `${Math.max(12, busySessionCount * 7 + sessions.length * 2)} RPM`,
                  direction: busySessionCount > 0 ? 'up' : 'neutral',
                }}
                secondaryLabel={t('nodes.kpiWorkloadSecondaryLabel')}
                secondaryValue={t('nodes.kpiWorkloadSecondaryValue', {
                  count: totalRequestsServed,
                })}
                onClick={() => handleNavigateSection('sessions')}
              />

              <DashboardStatCard
                title={t('nodes.kpiHealthyProxiesTitle')}
                value={`${activeCount} / ${proxies.length}`}
                subtitle={t('nodes.kpiHealthyProxiesSubtitle')}
                icon={<Globe size={18} />}
                variant="success"
                badge={
                  proxies.length - activeCount > 0
                    ? t('nodes.kpiCooldownCount', {
                        count: proxies.length - activeCount,
                      })
                    : t('nodes.kpiAllActive')
                }
                progress={Math.round(
                  (activeCount / Math.max(1, proxies.length)) * 100
                )}
                secondaryLabel={t('nodes.kpiActiveRatioLabel')}
                secondaryValue={`%${Math.round((activeCount / Math.max(1, proxies.length)) * 100)}`}
                onClick={() => handleNavigateSection('proxies')}
              />

              <DashboardStatCard
                title={t('nodes.kpiLatencyTitle')}
                value={`${avgLatency} ms`}
                subtitle={t('nodes.kpiLatencySubtitle')}
                icon={<Activity size={18} />}
                variant="info"
                trend={{
                  value:
                    avgLatency <= 80
                      ? t('nodes.kpiLatencyOptimal')
                      : t('nodes.kpiLatencyNormal'),
                  direction: avgLatency <= 80 ? 'down' : 'neutral',
                }}
                secondaryLabel={t('nodes.kpiAutoscaleLabel')}
                secondaryValue={t('nodes.kpiAutoscaleValue', {
                  count: activityFeedEvents.length,
                })}
              />
            </div>

            <div className="dashboard-grid-2">
              <DashboardTimelineChartView
                title={t('nodes.chartSessionsTitle')}
                subtitle={t('nodes.chartSessionsSubtitle', {
                  max: maxConcurrentBrowsers,
                })}
                icon={<MonitorCheck size={17} />}
                badge={t('nodes.chartTelemetryBadge')}
                data={timelinePoints}
                xKey="time_label"
                maxY={maxConcurrentBrowsers}
                height={190}
                series={[
                  {
                    key: 'total_sessions',
                    label: t('nodes.seriesTotalSessions'),
                    color: '#6366f1',
                    type: 'area',
                  },
                  {
                    key: 'active_busy_sessions',
                    label: t('nodes.seriesBusySessions'),
                    color: '#f59e0b',
                    type: 'line',
                  },
                  {
                    key: 'dynamic_sessions',
                    label: t('nodes.seriesDynamicSessions'),
                    color: '#10b981',
                    type: 'line',
                  },
                ]}
              />

              <DashboardTimelineChartView
                title={t('nodes.chartRpmTitle')}
                subtitle={t('nodes.chartRpmSubtitle')}
                icon={<Activity size={17} />}
                badge={t('nodes.chartAvgBadge', { ms: avgLatency })}
                data={timelinePoints}
                xKey="time_label"
                height={190}
                series={[
                  {
                    key: 'requests_per_min',
                    label: t('nodes.seriesRpm'),
                    color: '#3b82f6',
                    type: 'area',
                  },
                  {
                    key: 'avg_proxy_latency_ms',
                    label: t('nodes.seriesAvgLatency'),
                    color: '#ec4899',
                    type: 'line',
                  },
                ]}
              />
            </div>

            <div className="dashboard-grid-3">
              <DashboardDistributionView
                title={t('nodes.distProviderTitle')}
                subtitle={t('nodes.distProviderSubtitle')}
                icon={<Server size={17} />}
                badge={t('nodes.distProviderBadge', {
                  count: sessions.length,
                })}
                items={providerDistributionItems}
              />

              <DashboardDistributionView
                title={t('nodes.distRegionTitle')}
                subtitle={t('nodes.distRegionSubtitle')}
                icon={<Globe size={17} />}
                badge={t('nodes.distRegionBadge', { count: proxies.length })}
                items={proxyRegionDistributionItems}
              />

              <DashboardActivityFeedView
                title={t('nodes.feedTitle')}
                subtitle={t('nodes.feedSubtitle')}
                icon={<Zap size={17} />}
                badge={t('nodes.feedBadge', {
                  count: activityFeedEvents.length,
                })}
                events={activityFeedEvents}
                maxItems={4}
              />
            </div>
          </div>
        )}

        {isSessionsView && (
          <div className="grid-auto-320 gap-16">
            {filteredSessions.map((s) => {
              const isIdle = s.status === 'idle';
              const isDynamic = Boolean(s.is_dynamic);
              return (
                <BaseSystemCard
                  key={s.id}
                  icon={isDynamic ? <Zap size={20} /> : <MonitorCheck size={20} />}
                  iconBoxVariant={
                    isIdle ? (isDynamic ? 'primary' : 'success') : 'warning'
                  }
                  borderHighlight={
                    isDynamic
                      ? 'border-l-primary'
                      : isIdle
                        ? 'border-l-success'
                        : 'border-l-warning'
                  }
                  title={s.id}
                  subtitle={s.provider}
                  isDefault={true}
                  defaultPillText={
                    isDynamic ? t('nodes.pillDynamic') : t('nodes.pillWarm')
                  }
                  actions={[
                    {
                      label: t('nodes.terminateSessionAction'),
                      icon: <Trash2 size={15} />,
                      variant: 'danger',
                      onClick: () => handleConfirmTerminateSession(s),
                    },
                  ]}
                  details={[
                    { label: t('nodes.detailAccount'), value: s.account },
                    { label: t('nodes.detailAssignedProxy'), value: s.proxy },
                    {
                      label: t('nodes.detailSessionMode'),
                      value: isDynamic
                        ? t('nodes.detailModeDynamicValue', {
                            ttl: s.idle_ttl_sec || 300,
                          })
                        : t('nodes.detailModeWarmValue'),
                    },
                    {
                      label: t('nodes.detailRequestsServed'),
                      value: t('nodes.requestsServed', {
                        count: s.requests_served,
                      }),
                    },
                  ]}
                  status={{
                    active: isIdle,
                    activeText: t('status.idle'),
                    passiveText: t('status.busy'),
                  }}
                />
              );
            })}
          </div>
        )}

        {isProxiesView && (
          <div className="flex-col gap-16">
            <div className="grid-auto-320 gap-16">
              {filteredProxies.map((p) => {
                const isActive = p.status === 'active';
                const isChecking = checkingProxyId === p.id;
                const latency = p.latency_ms ?? 45;
                return (
                  <BaseSystemCard
                    key={p.id}
                    icon={<Globe size={20} />}
                    iconBoxVariant={isActive ? 'primary' : 'danger'}
                    borderHighlight={
                      isActive ? 'border-l-success' : 'border-l-danger'
                    }
                    title={p.endpoint}
                    subtitle={`${p.country}${p.city ? ` · ${p.city}` : ''} · ${p.provider || 'Custom Node'}`}
                    isDefault={true}
                    defaultPillText={(p.protocol || 'http').toUpperCase()}
                    actions={[
                      {
                        label: isChecking
                          ? t('nodes.checkingAll')
                          : t('nodes.checkProxy'),
                        icon: <Wifi size={15} />,
                        onClick: () => handleCheckSingleProxy(p.id),
                      },
                      {
                        label: t('nodes.toggleProxy'),
                        icon: <RefreshCw size={15} />,
                        onClick: () => handleToggleSingleProxy(p.id),
                      },
                      {
                        label: t('nodes.deleteProxy'),
                        icon: <Trash2 size={15} />,
                        variant: 'danger',
                        onClick: () => handleDeleteProxy(p),
                      },
                    ]}
                    details={[
                      { label: t('nodes.nodeIdLabel'), value: p.id },
                      {
                        label: t('nodes.fieldType'),
                        value: getProxyTypeLabel(p.proxy_type),
                      },
                      {
                        label: t('nodes.fieldCountry'),
                        value: `${p.country}${p.city ? ` · ${p.city}` : ''}`,
                      },
                      {
                        label: t('nodes.avgLatency'),
                        value: `${latency} ms`,
                      },
                    ]}
                    status={{
                      active: isActive,
                      activeText: t('status.active'),
                      passiveText: t('status.cooldown'),
                    }}
                  />
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Tekil veya Toplu Proxy Ekleme Popup (@akalin/ui BasePopup + BaseDropdownSecici + BaseInput + NotInput) */}
      <BasePopup
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={t('nodes.modalTitle')}
        modalSize="lg"
        isSaving={submitting}
        submitButtonText={
          modalTabId === 1 ? t('nodes.saveProxyBtn') : t('nodes.importListBtn')
        }
        onSave={handleSaveModal}
      >
        <div ref={proxyModalContainerRef} className="flex-col gap-16">
          <TabLayout
            tabs={[
              {
                id: 1,
                title: t('nodes.tabSingle'),
                icon: <ShieldCheck size={15} />,
              },
              {
                id: 2,
                title: t('nodes.tabBulk'),
                icon: <Server size={15} />,
              },
            ]}
            activeTabId={modalTabId}
            onTabChange={(id) => {
              setFormErrors({});
              setModalTabId(Number(id));
            }}
          />

          {modalTabId === 1 ? (
            <div className="flex-col gap-16">
              <div className="form-grid-2">
                <div className="form-group">
                  <label>{t('nodes.fieldProtocol')}</label>
                  <BaseDropdownSecici
                    value={singleForm.protocol}
                    options={PROXY_PROTOCOL_OPTIONS}
                    clearable={false}
                    onChange={(id) =>
                      setSingleForm((prev) => ({
                        ...prev,
                        protocol: String(id || 'socks5'),
                      }))
                    }
                  />
                </div>

                <div className="form-group">
                  <label>{t('nodes.fieldEndpoint')}</label>
                  <BaseInput
                    required
                    value={singleForm.endpoint}
                    onChange={(e) => {
                      clearFieldError('endpoint');
                      setSingleForm((prev) => ({
                        ...prev,
                        endpoint: e.target.value,
                      }));
                    }}
                    onBlur={() => {
                      const err = validateSingleProxyField(
                        'endpoint',
                        singleForm.endpoint,
                        t
                      );
                      if (err) {
                        setFormErrors((prev) => ({ ...prev, endpoint: err }));
                      }
                    }}
                    placeholder="185.220.101.5:1080"
                  />
                  <FieldError error={formErrors.endpoint} />
                </div>
              </div>

              <div className="form-grid-2">
                <div className="form-group">
                  <label>{t('nodes.fieldCountry')}</label>
                  <BaseDropdownSecici
                    value={singleForm.country}
                    options={PROXY_COUNTRY_OPTIONS}
                    clearable={false}
                    onChange={(id) => {
                      clearFieldError('country');
                      setSingleForm((prev) => ({
                        ...prev,
                        country: String(id || 'TR'),
                      }));
                    }}
                  />
                  <FieldError error={formErrors.country} />
                </div>

                <div className="form-group">
                  <label>{t('nodes.fieldCity')}</label>
                  <BaseInput
                    value={singleForm.city}
                    onChange={(e) =>
                      setSingleForm((prev) => ({
                        ...prev,
                        city: e.target.value,
                      }))
                    }
                    placeholder="Istanbul / Frankfurt / NYC"
                  />
                </div>
              </div>

              <div className="form-grid-2">
                <div className="form-group">
                  <label>{t('nodes.fieldType')}</label>
                  <BaseDropdownSecici
                    value={singleForm.proxyType}
                    options={proxyTypeOptions}
                    clearable={false}
                    onChange={(id) =>
                      setSingleForm((prev) => ({
                        ...prev,
                        proxyType: String(id || 'residential'),
                      }))
                    }
                  />
                </div>

                <div className="form-group">
                  <label>{t('nodes.fieldProvider')}</label>
                  <BaseInput
                    value={singleForm.provider}
                    onChange={(e) =>
                      setSingleForm((prev) => ({
                        ...prev,
                        provider: e.target.value,
                      }))
                    }
                    placeholder="BrightData / Oxylabs / Custom"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-col gap-16">
              <div className="dashboard-grid-3">
                <div className="form-group">
                  <label>{t('nodes.fieldProtocol')}</label>
                  <BaseDropdownSecici
                    value={bulkForm.bulkProtocol}
                    options={PROXY_PROTOCOL_OPTIONS}
                    clearable={false}
                    onChange={(id) =>
                      setBulkForm((prev) => ({
                        ...prev,
                        bulkProtocol: String(id || 'socks5'),
                      }))
                    }
                  />
                </div>
                <div className="form-group">
                  <label>{t('nodes.fieldCountry')}</label>
                  <BaseInput
                    value={bulkForm.bulkCountry}
                    onChange={(e) =>
                      setBulkForm((prev) => ({
                        ...prev,
                        bulkCountry: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="form-group">
                  <label>{t('nodes.fieldType')}</label>
                  <BaseDropdownSecici
                    value={bulkForm.bulkType}
                    options={proxyTypeOptions}
                    clearable={false}
                    onChange={(id) =>
                      setBulkForm((prev) => ({
                        ...prev,
                        bulkType: String(id || 'residential'),
                      }))
                    }
                  />
                </div>
              </div>

              <div className="form-group">
                <label>{t('nodes.bulkLabel')}</label>
                <NotInput
                  rows={6}
                  value={bulkForm.bulkList}
                  onChange={(e) => {
                    clearFieldError('bulkList');
                    setBulkForm((prev) => ({
                      ...prev,
                      bulkList: e.target.value,
                    }));
                  }}
                  onBlur={() => {
                    const err = validateBulkProxyField(
                      'bulkList',
                      bulkForm.bulkList,
                      t
                    );
                    if (err) {
                      setFormErrors((prev) => ({ ...prev, bulkList: err }));
                    }
                  }}
                  placeholder={t('nodes.bulkPlaceholder')}
                />
                <FieldError error={formErrors.bulkList} />
              </div>
            </div>
          )}
        </div>
      </BasePopup>

      {/* Dinamik Tarayıcı Oturumu Başlatma Popup (@akalin/ui BasePopup + BaseDropdownSecici + BaseInput + TamsayiInput) */}
      <BasePopup
        isOpen={isSpawnModalOpen}
        onClose={() => setIsSpawnModalOpen(false)}
        title={t('nodes.spawnModalTitle')}
        modalSize="md"
        isSaving={spawningSession}
        submitButtonText={t('nodes.spawnModalSubmitBtn')}
        onSave={handleSpawnSessionModal}
      >
        <div ref={spawnModalContainerRef} className="flex-col gap-16">
          <div className="form-group">
            <label>{t('nodes.spawnFieldProvider')}</label>
            <BaseDropdownSecici
              value={spawnForm.spawnProvider}
              options={SPAWN_PROVIDER_OPTIONS}
              clearable={false}
              onChange={(id) => {
                clearFieldError('spawnProvider');
                setSpawnForm((prev) => ({
                  ...prev,
                  spawnProvider: String(id || 'chatgpt-web'),
                }));
              }}
            />
            <FieldError error={formErrors.spawnProvider} />
          </div>

          <div className="form-group">
            <label>{t('nodes.spawnFieldProxy')}</label>
            <BaseDropdownSecici
              value={spawnForm.spawnProxyId}
              options={spawnProxyOptions}
              clearable={true}
              onChange={(id) =>
                setSpawnForm((prev) => ({
                  ...prev,
                  spawnProxyId: String(id ?? ''),
                }))
              }
            />
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label>{t('nodes.spawnFieldAccount')}</label>
              <BaseInput
                value={spawnForm.spawnAccount}
                onChange={(e) =>
                  setSpawnForm((prev) => ({
                    ...prev,
                    spawnAccount: e.target.value,
                  }))
                }
                placeholder={t('nodes.spawnFieldAccountPlaceholder')}
              />
            </div>

            <div className="form-group">
              <label>{t('nodes.spawnFieldTtl')}</label>
              <TamsayiInput
                value={spawnForm.spawnIdleTtl}
                onChange={(e) => {
                  clearFieldError('spawnIdleTtl');
                  setSpawnForm((prev) => ({
                    ...prev,
                    spawnIdleTtl: Number(e.target.value) || 300,
                  }));
                }}
                placeholder="300"
              />
              <FieldError error={formErrors.spawnIdleTtl} />
            </div>
          </div>
        </div>
      </BasePopup>
    </BasePage>
  );
};

NodesPoolView.hasExternalSettings = true;

export const NodesPoolPage = NodesPoolView;
export default NodesPoolPage;
