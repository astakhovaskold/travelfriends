import {createSignal} from 'solid-js';
import {platform} from '../platform/telegram';
import {guessLang, LANGS, T} from './dictionaries';

export {guessLang, LANGS, T};

function initialLanguage() {
  try {
    const value = localStorage.getItem('l');
    if (value && T[value]) {
      return value;
    }
  } catch {
  }
  return guessLang(platform.user.language_code);
}

export const [language, updateLanguage] = createSignal(initialLanguage());

export function setLanguage(value: string) {
  if (!T[value]) {
    return;
  }
  updateLanguage(value);
  document.documentElement.lang = value;
  try {
    localStorage.setItem('l', value);
  } catch {
  }
}

export function translate(lang: string, key: string): string {
  const value = T[lang]?.[key] ?? T.en[key];
  return typeof value === 'string' ? value : '';
}

export const tx = (key: string) => translate(language(), key);
export const loc = () =>
  (
    ({
      ru: 'ru-RU',
      en: 'en-GB',
      de: 'de-DE',
      fr: 'fr-FR',
      it: 'it-IT',
      zh: 'zh-CN',
    }) as Record<string, string>
  )[language()];
export const fmt = (date: string) =>
  date
    ? new Date(date).toLocaleDateString(loc(), {
      day: 'numeric',
      month: 'short',
    })
    : '';
