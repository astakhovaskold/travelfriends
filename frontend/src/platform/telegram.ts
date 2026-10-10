interface TelegramUser {
  id?: number;
  first_name?: string;
  language_code?: string;
  photo_url?: string;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe?: {
    user?: TelegramUser;
  };
  HapticFeedback?: {
    impactOccurred(kind: string): void;
    notificationOccurred(kind: string): void;
  };

  ready(): void;

  expand(): void;

  setBackgroundColor?(color: string): void;

  setHeaderColor?(color: string): void;

  showConfirm?(text: string, callback: (confirmed: boolean) => void): void;

  openTelegramLink?(url: string): void;

  openInvoice?(link: string, callback: (status: string) => void): void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}
const sdk = () =>
  typeof window === 'undefined' ? undefined : window.Telegram?.WebApp;
export const platform = {
  get initData() {
    return sdk()?.initData || '';
  },
  get user() {
    return sdk()?.initDataUnsafe?.user || {};
  },
  initialize() {
    try {
      sdk()?.ready();
      sdk()?.expand();
      sdk()?.setBackgroundColor?.('#FBF6EC');
      sdk()?.setHeaderColor?.('#FBF6EC');
    } catch {
      /* Older Telegram clients may omit capabilities. */
    }
  },
  haptic(kind = 'light') {
    try {
      sdk()?.HapticFeedback?.impactOccurred(kind);
    } catch {
    }
  },
  success() {
    try {
      sdk()?.HapticFeedback?.notificationOccurred('success');
    } catch {
    }
  },
  confirm(text: string, action: () => void) {
    const tg = sdk();
    if (tg?.showConfirm) {
      tg.showConfirm(text, (ok) => {
        if (ok) {
          action();
        }
      });
    } else if (window.confirm(text)) {
      action();
    }
  },
  share(url: string) {
    if (sdk()?.openTelegramLink) {
      sdk()?.openTelegramLink?.(url);
    } else {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  },
  invoice(link: string, callback: (status: string) => void) {
    if (!sdk()?.openInvoice) {
      throw new Error('badreq');
    }
    sdk()?.openInvoice?.(link, callback);
  },
};
