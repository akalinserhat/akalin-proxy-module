/**
 * @file useProxyAutoFocus.ts
 * @description @akalin/proxy_module - Proxy ve Oturum popuplarında açılışta ve sekme
 * değişimlerinde ilk etkileşimli alana otomatik odaklanma kancası.
 */

import { useEffect, RefObject } from 'react';
import { autoFocusFirstInput } from '@akalin/ui';

export function useProxyAutoFocus(
  containerRef: RefObject<HTMLElement | null>,
  triggerDeps: ReadonlyArray<unknown>
): void {
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (containerRef.current) {
        autoFocusFirstInput(containerRef.current);
      }
    }, 60);
    return () => window.clearTimeout(timer);
  }, triggerDeps);
}
