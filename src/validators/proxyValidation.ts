/**
 * @file proxyValidation.ts
 * @description @akalin/proxy_module - Tekil Proxy, Toplu Proxy İçe Aktarma ve Dinamik Oturum
 * formları için saf (pure) doğrulama fonksiyonları.
 */

import {
  BulkProxyFormState,
  SingleProxyFormState,
  SpawnSessionFormState,
} from '../defaults/proxyDefaultValue';

const ENDPOINT_PORT_REGEX = /^[^\s:]+:\d{1,5}$/;

export function validateSingleProxyField(
  field: keyof SingleProxyFormState,
  value: unknown,
  translate?: (key: string) => string
): string {
  const t = translate || ((k: string) => k);
  const str = String(value ?? '').trim();

  if (field === 'endpoint') {
    if (!str) {
      return t('nodes.validationEndpointRequired');
    }
    if (!ENDPOINT_PORT_REGEX.test(str)) {
      return t('nodes.validationEndpointFormat');
    }
  }

  if (field === 'country' && !str) {
    return t('nodes.validationCountryRequired');
  }

  return '';
}

export function validateSingleProxyForm(
  data: SingleProxyFormState,
  translate?: (key: string) => string
): Record<string, string> {
  const errors: Record<string, string> = {};
  const endpointErr = validateSingleProxyField('endpoint', data.endpoint, translate);
  if (endpointErr) errors.endpoint = endpointErr;

  const countryErr = validateSingleProxyField('country', data.country, translate);
  if (countryErr) errors.country = countryErr;

  return errors;
}

export function validateBulkProxyField(
  field: keyof BulkProxyFormState,
  value: unknown,
  translate?: (key: string) => string
): string {
  const t = translate || ((k: string) => k);
  const str = String(value ?? '').trim();

  if (field === 'bulkList' && !str) {
    return t('nodes.validationBulkListRequired');
  }

  return '';
}

export function validateBulkProxyForm(
  data: BulkProxyFormState,
  translate?: (key: string) => string
): Record<string, string> {
  const errors: Record<string, string> = {};
  const listErr = validateBulkProxyField('bulkList', data.bulkList, translate);
  if (listErr) errors.bulkList = listErr;
  return errors;
}

export function validateSpawnSessionField(
  field: keyof SpawnSessionFormState,
  value: unknown,
  translate?: (key: string) => string
): string {
  const t = translate || ((k: string) => k);
  if (field === 'spawnProvider' && !String(value ?? '').trim()) {
    return t('nodes.validationProviderRequired');
  }
  if (field === 'spawnIdleTtl') {
    const num = Number(value);
    if (!Number.isFinite(num) || num < 30) {
      return t('nodes.validationTtlMin');
    }
  }
  return '';
}

export function validateSpawnSessionForm(
  data: SpawnSessionFormState,
  translate?: (key: string) => string
): Record<string, string> {
  const errors: Record<string, string> = {};
  const provErr = validateSpawnSessionField('spawnProvider', data.spawnProvider, translate);
  if (provErr) errors.spawnProvider = provErr;

  const ttlErr = validateSpawnSessionField('spawnIdleTtl', data.spawnIdleTtl, translate);
  if (ttlErr) errors.spawnIdleTtl = ttlErr;

  return errors;
}
