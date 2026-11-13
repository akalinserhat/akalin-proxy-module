/**
 * @file NodesPoolPageSettingsForExternal.tsx
 * @description @akalin/proxy_module - Flowchart Düğümleri (FORM_AC vb.) ve Dış Bileşenler
 * için Bağlantı & Proxy Havuzu Harici Düğüm Ayar Sayfası (`hasExternalSettings = true`).
 */

import React, { useState, useMemo } from 'react';
import { Globe } from 'lucide-react';
import {
  BaseCardPage,
  BaseDropdownSecici,
  BaseSwitch,
  type DropdownOption,
} from '@akalin/ui';
import { PROXY_PROTOCOL_OPTIONS } from '../defaults/proxyDefaultValue';
import { useProxyTranslation } from '../i18n/proxyTranslations';

export interface NodesPoolExternalSettingsValue {
  defaultSection: 'dashboard' | 'sessions' | 'proxies';
  defaultProtocolFilter: string;
  autoCheckOnOpen: boolean;
}

export interface NodesPoolPageSettingsForExternalProps {
  value?: Partial<NodesPoolExternalSettingsValue>;
  onChange?: (next: NodesPoolExternalSettingsValue) => void;
  onSave?: (next: NodesPoolExternalSettingsValue) => void;
  onClose?: () => void;
  inModal?: boolean;
}

export const NodesPoolPageSettingsForExternal: React.FC<
  NodesPoolPageSettingsForExternalProps
> = ({ value, onChange, onSave, onClose, inModal = false }) => {
  const { t } = useProxyTranslation();

  const [formState, setFormState] = useState<NodesPoolExternalSettingsValue>({
    defaultSection: value?.defaultSection || 'proxies',
    defaultProtocolFilter: value?.defaultProtocolFilter || 'all',
    autoCheckOnOpen: Boolean(value?.autoCheckOnOpen ?? false),
  });

  const sectionOptions = useMemo<DropdownOption[]>(
    () => [
      { id: 'dashboard', value: 'dashboard', label: t('nav.nodesDashboard') },
      { id: 'sessions', value: 'sessions', label: t('nav.nodesSessions') },
      { id: 'proxies', value: 'proxies', label: t('nav.nodesProxies') },
    ],
    [t]
  );

  const protocolOptions = useMemo<DropdownOption[]>(
    () => [
      { id: 'all', value: 'all', label: t('nodes.protocolAll') },
      ...PROXY_PROTOCOL_OPTIONS,
    ],
    [t]
  );

  const updateState = (patch: Partial<NodesPoolExternalSettingsValue>) => {
    const next = { ...formState, ...patch };
    setFormState(next);
    if (onChange) {
      onChange(next);
    }
  };

  return (
    <BaseCardPage
      title={t('nodes.externalSettingsTitle')}
      subtitle={t('nodes.externalSettingsSubtitle')}
      icon={<Globe size={20} />}
      inModal={inModal}
      showBackButton={Boolean(onClose)}
      onClose={onClose}
      onSave={onSave ? () => onSave(formState) : undefined}
    >
      <div className="flex-col gap-16">
        <div className="form-grid-2">
          <div className="form-group">
            <label>{t('nodes.externalDefaultSection')}</label>
            <BaseDropdownSecici
              value={formState.defaultSection}
              options={sectionOptions}
              clearable={false}
              onChange={(id) =>
                updateState({
                  defaultSection: (id as 'dashboard' | 'sessions' | 'proxies') || 'proxies',
                })
              }
            />
          </div>

          <div className="form-group">
            <label>{t('nodes.externalDefaultProtocol')}</label>
            <BaseDropdownSecici
              value={formState.defaultProtocolFilter}
              options={protocolOptions}
              clearable={false}
              onChange={(id) =>
                updateState({ defaultProtocolFilter: String(id || 'all') })
              }
            />
          </div>
        </div>

        <div className="form-group">
          <BaseSwitch
            checked={formState.autoCheckOnOpen}
            onChange={(e) => updateState({ autoCheckOnOpen: e.target.checked })}
            label={t('nodes.externalAutoCheckOnOpen')}
          />
        </div>
      </div>
    </BaseCardPage>
  );
};

export default NodesPoolPageSettingsForExternal;
