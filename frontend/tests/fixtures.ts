import {readFileSync} from 'node:fs';
import {expect, type Page} from '@playwright/test';
import type {Message, Reactions, Trip} from '../src/api/types';
import '../src/platform/telegram';

declare global {
  interface Window {
    __telegramCalls: unknown[][];
  }
}
export const NOW = '2026-10-11T12:00:00Z';
export const user = {
  id: 7,
  name: 'Alex',
  age: 29,
  city: 'Madrid',
  about: 'Love trains and mountains',
  vibe: 'nature,food',
  rules_ok: 1,
  registered: 1,
  trips: 12,
  friends: 8,
  cnt: 3,
  avg: 4.7,
};
export const trip = {
  id: 1,
  user_id: 8,
  author_id: 8,
  dest: 'Paris',
  country: 'France',
  kind: 'flight',
  name: 'Maria',
  age: 28,
  a_cnt: 2,
  a_avg: 4.5,
  date_from: '2026-11-01',
  date_to: '2026-11-08',
  people: 3,
  members: 1,
  mine: false,
  joined: 0,
  closed: 0,
  ended: false,
  created: Date.parse(NOW) / 1000 - 1000,
  boosted: 0,
  budget: '€800',
  note: 'Museums and good food',
  about: 'Let’s explore together',
  city: 'Rome',
  a_vibe: 'nature,food',
  audience: 'all',
  min_age: 18,
  max_age: 40,
  approval: 0,
  pending: 0,
  req: null,
  chat_open: 1,
  to_rate: 0,
};
export const owned = {
  ...trip,
  id: 2,
  dest: 'Rome',
  kind: 'train',
  mine: true,
  user_id: 7,
  author_id: 7,
  name: 'Alex',
  pending: 1,
};
export const members = [
  {
    id: 7,
    name: 'Alex',
    age: 29,
    is_author: true,
    a_cnt: 3,
    a_avg: 4.7,
    rated: 0,
  },
  {
    id: 8,
    name: 'Maria',
    age: 28,
    is_author: false,
    a_cnt: 2,
    a_avg: 4.5,
    rated: 0,
  },
];
export type Scenario =
  | 'ready'
  | 'empty'
  | 'onboarding'
  | 'registration'
  | 'minor'
  | 'error'
  | 'ended'
  | 'approval'
  | 'full';

export async function setup(
  page: Page,
  language = 'en',
  scenario: Scenario = 'ready',
) {
  await page.clock.install({
    time: new Date(NOW),
  });
  await page.addInitScript(
    ({language}) => {
      localStorage.setItem('l', language);
      const calls: unknown[][] = [];
      window.__telegramCalls = calls;
      const record =
        (name: string) =>
          (...args: unknown[]) =>
            calls.push([
              name,
              ...args,
            ]);
      window.Telegram = {
        WebApp: {
          initData: 'test-init-data',
          initDataUnsafe: {
            user: {
              id: 999,
              first_name: 'Alex',
              language_code: language,
            },
          },
          ready: record('ready'),
          expand: record('expand'),
          setBackgroundColor: record('background'),
          setHeaderColor: record('header'),
          HapticFeedback: {
            impactOccurred: record('impact'),
            notificationOccurred: record('notification'),
          },
          openTelegramLink: record('link'),
          showConfirm: (text: string, cb: (ok: boolean) => void) => {
            calls.push([
              'confirm',
              text,
            ]);
            cb(true);
          },
          openInvoice: (link: string, cb: (s: string) => void) => {
            calls.push([
              'invoice',
              link,
            ]);
            cb('paid');
          },
        },
      };
    },
    {
      language,
    },
  );
  const requests: {
    path: string;
    method: string;
    body: unknown;
  }[] = [];
  let accepted = false;
  let joined = false;
  let rules = scenario !== 'onboarding';
  let registered = scenario !== 'registration' && scenario !== 'onboarding';
  const sent: Message[] = [];
  const reactions: Reactions = {};
  const created: Trip[] = [];
  let profile = {
    ...user,
  };
  const item = () => ({
    ...trip,
    ...(scenario === 'ended'
      ? {
        ended: true,
        joined: 1,
        to_rate: 1,
      }
      : {}),
    ...(scenario === 'approval'
      ? {
        approval: 1,
      }
      : {}),
    ...(scenario === 'full'
      ? {
        members: 3,
      }
      : {}),
    ...(joined
      ? {
        joined: 1,
        members: 2,
      }
      : {}),
  });
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    const origin =
      process.env.FRONTEND_TARGET === 'production'
        ? 'http://127.0.0.1:5174'
        : 'http://127.0.0.1:5173';
    if (url.origin === origin && !url.pathname.startsWith('/api/')) {
      return route.continue();
    }
    if (url.hostname === 'telegram.org') {
      return route.fulfill({
        contentType: 'application/javascript',
        body: '',
      });
    }
    if (url.hostname === 'fonts.googleapis.com') {
      const css = [
        500,
        700,
        800,
      ]
        .map((weight) =>
          readFileSync(
            new URL(
              `../node_modules/@fontsource/bricolage-grotesque/${weight}.css`,
              import.meta.url,
            ),
            'utf8',
          ).replaceAll(
            './files/',
            'http://127.0.0.1:5173/node_modules/@fontsource/bricolage-grotesque/files/',
          ),
        )
        .join('\n');
      return route.fulfill({
        contentType: 'text/css',
        body: css,
      });
    }
    if (url.hostname === 'en.wikipedia.org') {
      return route.fulfill({
        json: {},
      });
    }
    if (!url.pathname.startsWith('/api/')) {
      return route.abort();
    }
    const path = url.pathname.slice(4);
    const method = route.request().method();
    const body = route.request().postDataJSON();
    requests.push({
      path,
      method,
      body,
    });
    if (
      path !== '/config' &&
      route.request().headers()['x-init-data'] !== 'test-init-data'
    ) {
      throw new Error('Missing legacy authentication header');
    }
    const ok = (json: unknown) =>
      route.fulfill({
        json,
      });
    const fail = (detail: string, status = 403) =>
      route.fulfill({
        status,
        json: {
          detail,
        },
      });
    if (scenario === 'minor' && path !== '/config') {
      return fail('minor');
    }
    if (path === '/config') {
      return ok({
        bot: 'travel_test_bot',
      });
    }
    if (path === '/me') {
      return ok({
        ...profile,
        rules_ok: +rules,
        registered: +registered,
      });
    }
    if (path === '/rules') {
      rules = true;
      return ok({
        ok: true,
      });
    }
    if (path === '/register') {
      registered = true;
      return ok({
        ok: true,
      });
    }
    if (path === '/profile') {
      profile = {
        ...profile,
        ...body,
        vibe: body.vibe.join(','),
      };
      return ok({
        ok: true,
      });
    }
    if (!rules) {
      return fail('rules');
    }
    if (!registered) {
      return fail('register');
    }
    if (path === '/trips' && method === 'POST') {
      created.push({
        ...owned,
        ...body,
        id: 3,
      });
      return ok({
        ok: true,
      });
    }
    if (path === '/trips') {
      return scenario === 'error'
        ? fail('banned')
        : ok(
          scenario === 'empty'
            ? []
            : [
              item(),
              owned,
            ],
        );
    }
    if (path === '/my') {
      return ok({
        mine: [
          owned,
          ...created,
        ],
        joined: [
          item(),
        ],
      });
    }
    if (/\/boost$/.test(path)) {
      return ok({
        link: 'https://t.me/$test-invoice',
      });
    }
    if (/\/join$/.test(path)) {
      joined = true;
      return ok({
        pending: scenario === 'approval',
      });
    }
    if (/\/requests\/\d+\//.test(path)) {
      accepted = true;
      return ok({
        ok: true,
      });
    }
    if (/\/requests$/.test(path)) {
      return ok(
        accepted
          ? []
          : [
            {
              id: 8,
              name: 'Maria',
              age: 28,
              a_cnt: 2,
              a_avg: 4.5,
            },
          ],
      );
    }
    if (/\/people$/.test(path)) {
      return ok({
        dest: 'Paris',
        me: 7,
        author_id: 7,
        ended: true,
        closed: false,
        members,
      });
    }
    if (/\/chat$/.test(path)) {
      return ok({
        dest: 'Paris',
        me: 7,
        author_id: 7,
        ended: false,
        closed: false,
        members,
        messages: [
          {
            id: 1,
            user_id: 8,
            name: 'Maria',
            text: 'Hello Alex!',
            created: 1,
          },
          ...sent,
        ].filter((m) => m.id > +(url.searchParams.get('since') || 0)),
        reactions,
      });
    }
    if (/\/messages$/.test(path)) {
      sent.push({
        id: 2 + sent.length,
        user_id: 7,
        name: 'Alex',
        text: body.text,
        created: 2,
      });
      return ok({
        ok: true,
      });
    }
    if (/\/react$/.test(path)) {
      const id = path.split('/')[2];
      reactions[id] = {
        [body.emoji]: [
          1,
          1,
        ],
      };
      return ok({
        ok: true,
      });
    }
    if (/^\/users\/\d+$/.test(path)) {
      return ok({
        ...user,
        id: 8,
        name: 'Maria',
        city: 'Rome',
        vibe: [
          'nature',
          'food',
        ],
        tags: {
          reliable: 2,
        },
        me: path === '/users/7',
        blocked: false,
        reviews: [
          {
            stars: 5,
            name: 'Alex',
            dest: 'Paris',
            tags: [
              'reliable',
            ],
            text: 'Great trip!',
          },
        ],
      });
    }
    if (/^\/trips\/\d+$/.test(path)) {
      return ok(path === '/trips/2' ? owned : item());
    }
    if (method === 'POST') {
      return ok({
        ok: true,
      });
    }
    throw new Error(`Unhandled fixture: ${method} ${path}`);
  });
  return requests;
}

export async function open(page: Page, query = '', splash = false) {
  const target =
    process.env.FRONTEND_TARGET === 'legacy'
      ? '/legacy/index.html'
      : process.env.FRONTEND_TARGET === 'production'
        ? '/'
        : '/';
  await page.goto(target + query);
  await expect(page.locator('#app .top')).toBeVisible();
  if (!splash) {
    await page.locator('#splash h1').click();
    await page.clock.runFor(3000);
    await expect(page.locator('#splash')).toHaveClass(/out/);
  }
}

export async function shot(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () =>
        [
          ...document.fonts,
        ].filter((font) => font.status === 'error').length,
    ),
  ).toBe(0);
  await expect(page).toHaveScreenshot(`${name}.png`);
}
