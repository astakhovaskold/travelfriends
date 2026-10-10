import {describe, expect, it} from 'vitest';
import {errorDetail} from '../src/api/client';
import {
  type Message,
  mergeMessages,
  splitVibes,
  type Trip,
} from '../src/api/types';
import {filterTrips, pinCoord} from '../src/data/trips';
import {guessLang, translate} from '../src/i18n';

const trips = [
  {
    dest: 'Paris',
    country: 'France',
    kind: 'train',
  },
  {
    dest: 'Rome',
    country: 'Italy',
    kind: 'flight',
  },
] as Trip[];
describe('API boundary', () => {
  it('normalizes comma separated me.vibe and public arrays', () => {
    expect(splitVibes('nature,,food')).toEqual([
      'nature',
      'food',
    ]);
    expect(
      splitVibes([
        'food',
      ]),
    ).toEqual([
      'food',
    ]);
    expect(splitVibes(null)).toEqual([]);
  });
  it('renders backend error codes and FastAPI validation without object coercion', () => {
    expect(errorDetail('full')).toBe('full');
    expect(
      errorDetail([
        {
          msg: 'Invalid date',
        },
        {
          msg: 'Missing destination',
        },
      ]),
    ).toBe('Invalid date; Missing destination');
    expect(errorDetail({})).toBe('Error');
  });
  it('deduplicates and orders incremental chat messages', () => {
    const first = {
      id: 2,
      text: 'hello',
    };
    const second = {
      id: 1,
      text: 'first',
    };
    const updated = {
      id: 2,
      text: 'updated',
    };
    expect(
      mergeMessages(
        [
          first,
        ] as Message[],
        [
          second,
          updated,
        ] as Message[],
      ).map((m) => m.text),
    ).toEqual([
      'first',
      'updated',
    ]);
  });
});
describe('catalog', () => {
  it('searches Russian names and countries and combines kind and place', () => {
    expect(filterTrips(trips, 'Париж', 'all')).toEqual([
      trips[0],
    ]);
    expect(filterTrips(trips, 'France', 'flight')).toEqual([]);
    expect(filterTrips(trips, '', 'all', 'Rome')).toEqual([
      trips[1],
    ]);
  });
  it('prefers catalog coordinates and supports custom destinations', () => {
    expect(
      pinCoord({
        ...trips[0],
        lat: 0,
        lon: 0,
      }),
    ).toEqual([
      48.86,
      2.35,
    ]);
    expect(
      pinCoord({
        dest: 'Custom',
        lat: 12,
        lon: 25,
      } as Trip),
    ).toEqual([
      12,
      25,
    ]);
    expect(
      pinCoord({
        dest: 'Custom',
      } as Trip),
    ).toBeNull();
  });
});
describe('translations', () => {
  it('preserves language selection and English fallback', () => {
    expect(guessLang('uk')).toBe('ru');
    expect(guessLang('de-DE')).toBe('de');
    expect(guessLang('es')).toBe('en');
    expect(translate('missing', 'board')).toBe('Flights');
    expect(translate('zh', 'err_baddate_plan')).toBe(
      translate('en', 'err_baddate_plan'),
    );
  });
});
