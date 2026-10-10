import type {Trip} from '../api/types';
import {fmt, language, tx} from '../i18n';
import {CITY} from './cities';

export const byEn = Object.fromEntries(
  CITY.map((city) => [
    city.en,
    city,
  ]),
);
export const dn = (dest: string) =>
  byEn[dest] && language() === 'ru' ? byEn[dest].ru : dest;
export const KIND: Record<string, string> = {
  flight: '✈️',
  train: '🚆',
  road: '🚗',
  hike: '🥾',
  plan: '🔥',
  other: '🧭',
};
export const ke = (trip: Pick<Trip, 'kind'>) => KIND[trip.kind] || KIND.flight;
export const ci = (text: unknown) => {
  let hash = 0;
  for (const c of String(text).toLowerCase()) {
    hash = (hash * 31 + c.charCodeAt(0)) % 997;
  }
  return hash % 6;
};
export const range = (trip: Trip) =>
  trip.date_from
    ? fmt(trip.date_from) + (trip.date_to ? ` – ${fmt(trip.date_to)}` : '')
    : tx('flex');
export const yo = (age: number | null) => (age ? `${age} ${tx('yo')}` : '');
export const VIBES = [
  'early',
  'nature',
  'night',
  'museums',
  'spontaneous',
  'planner',
  'food',
  'photo',
  'active',
  'chill',
];
export const TAGS = [
  'reliable',
  'fun',
  'respectful',
  'organized',
  'punctual',
  'late',
  'rude',
];
export const NEG = new Set([
  'late',
  'rude',
]);
export const pinCoord = (
  trip: Trip,
):
  | [
  number,
  number,
]
  | null => {
  const city = byEn[trip.dest];
  return city
    ? [
      city.lat,
      city.lon,
    ]
    : trip.lat != null && trip.lon != null
      ? [
        trip.lat,
        trip.lon,
      ]
      : null;
};

export function filterTrips(
  list: Trip[],
  query: string,
  kind: string,
  place = '',
) {
  const needle = query.trim().toLowerCase();
  return list.filter((trip) => {
    const c = byEn[trip.dest];
    const hay = [
      trip.dest,
      trip.country || '',
      c?.ru || '',
      c?.cr || '',
    ]
      .join(' ')
      .toLowerCase();
    return (
      (kind === 'all' || trip.kind === kind) &&
      hay.includes(needle) &&
      (!place || trip.dest === place)
    );
  });
}
