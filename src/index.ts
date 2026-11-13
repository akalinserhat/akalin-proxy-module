/**
 * @file index.ts
 * @description @akalin/proxy_module - Bağımsız Bağlantı Havuzu, Anti-Bot Proxy Havuzu ve
 * Dinamik Tarayıcı Oturumları (Auto-Scale) Kütüphanesi Ana Giriş Noktası.
 * @akalin/module_core (`IModuleDefinition` / `ModuleRegistry`) ile %100 uyumludur.
 */

// 1. Sözleşme Tipleri (DTO & Interfaces)
export * from './types';

// 2. Varsayılan Değerler & Çekirdek Veriler
export {
  getSingleProxyDefaultValues,
  getBulkProxyDefaultValues,
  getSpawnSessionDefaultValues,
  PROXY_PROTOCOL_OPTIONS,
  PROXY_COUNTRY_OPTIONS,
  SPAWN_PROVIDER_OPTIONS,
  DEFAULT_SEED_SESSIONS,
  DEFAULT_SEED_PROXIES,
  buildDefaultPoolTimeline,
  type SingleProxyFormState,
  type BulkProxyFormState,
  type SpawnSessionFormState,
} from './defaults/proxyDefaultValue';

// 3. Saf Doğrulayıcılar (Pure Validators)
export {
  validateSingleProxyField,
  validateSingleProxyForm,
  validateBulkProxyField,
  validateBulkProxyForm,
  validateSpawnSessionField,
  validateSpawnSessionForm,
} from './validators/proxyValidation';

// 4. Odaklanma Kancası (AutoFocus Hook) ve Çok Dilli Çeviri (i18n)
export { useProxyAutoFocus } from './hooks/useProxyAutoFocus';
export {
  PROXY_MODULE_TRANSLATIONS,
  createProxyTranslator,
  useProxyTranslation,
  type SupportedProxyLocale,
} from './i18n/proxyTranslations';

// 5. Servis Adaptörleri, React Context & Doğrudan `proxyService` İstemcisi
export {
  createLocalStorageProxyAdapter,
  createRestProxyAdapter,
  ProxyModuleContext,
  ProxyModuleProvider,
  useProxyModule,
  setGlobalProxyModuleConfig,
  getGlobalProxyModuleConfig,
  proxyService,
  type ProxyModuleContextValue,
  type ProxyModuleProviderProps,
} from './adapters/ProxyServiceContext';

// 6. Sayfalar & Harici Düğüm Ayar Bileşenleri
export {
  NodesPoolView,
  NodesPoolPage,
  type NodesPoolPageComponent,
} from './pages/NodesPoolPage';
export {
  NodesPoolPageSettingsForExternal,
  type NodesPoolExternalSettingsValue,
  type NodesPoolPageSettingsForExternalProps,
} from './pages/NodesPoolPageSettingsForExternal';

// 7. @akalin/module_core Modül Fabrikası ve Varsayılan Manifestler
export {
  createProxyModule,
  ProxyModulu,
  ProxyManagementModule,
  default,
} from './createProxyModule';
