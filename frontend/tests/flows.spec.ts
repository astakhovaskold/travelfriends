import {expect, test} from '@playwright/test';
import {open, setup} from './fixtures';

test('search, filters, pins and zoom', async ({page}) => {
  await setup(page);
  await open(page);
  await expect(page.locator('#list .flt')).toHaveCount(2);
  const before = await page.locator('#map svg').getAttribute('style');
  await page.locator('#map [data-z="1"]').click();
  expect(await page.locator('#map svg').getAttribute('style')).not.toBe(before);
  await page.locator('#map .pw').first().click();
  await expect(page.locator('#list .flt')).toHaveCount(1);
  await expect(page.locator('#mclr')).toBeVisible();
  await page.locator('#mclr').click();
  await page.locator('#q').fill('Париж');
  await expect(page.locator('#list .flt')).toHaveCount(1);
  await page.locator('#q').fill('');
  await page.locator('#chips [data-k="train"]').click();
  await expect(page.locator('#list .flt')).toHaveCount(1);
  await expect(page.locator('#list')).toContainText('Rome');
});
test('create trip with city lookup and unchanged payload', async ({page}) => {
  const requests = await setup(page);
  await open(page);
  await page.locator('#plus').click();
  await page.locator('#dest').fill('Paris');
  await page.locator('#opts .opt').first().click();
  await page.locator('#df').fill('2026-11-01');
  await page.locator('#dt').fill('2026-11-08');
  await page.locator('#pp').fill('3');
  await page.locator('#bd').fill('€800');
  await page.locator('#nt').fill('Food and museums');
  await page.locator('#pub').click();
  await expect(page.locator('#edit')).toBeVisible();
  expect(
    requests.find((r) => r.path === '/trips' && r.method === 'POST')?.body,
  ).toMatchObject({
    dest: 'Paris',
    country: 'France',
    kind: 'flight',
    lat: 48.86,
    lon: 2.35,
    people: 3,
    note: 'Food and museums',
    approval: 0,
  });
});
test('join, chat message, reaction, reporting and share', async ({page}) => {
  const requests = await setup(page);
  await open(page);
  await page.locator('#list .flt').first().click();
  await page.locator('#acts .pri').click();
  await page.clock.runFor(1800);
  await expect(page.locator('#mi')).toBeVisible();
  await page.locator('#mi').fill('See you soon');
  await page.locator('#sb').click();
  await expect(page.locator('#msgs')).toContainText('See you soon');
  await page.locator('#msgs .rb').first().click();
  await page.locator('.pk [data-e="👍"]').click();
  await expect(page.locator('.rc')).toContainText('👍 1');
  await page.locator('.rp').click();
  await page.locator('#cm').click();
  await page.locator('#ps').click();
  expect(requests.some((r) => r.path === '/trips/1/join')).toBeTruthy();
  expect(requests.some((r) => r.path === '/messages/1/report')).toBeTruthy();
  expect(
    await page.evaluate(() =>
      window.__telegramCalls.some(
        (c: unknown[]) =>
          c[0] === 'link' &&
          typeof c[1] === 'string' &&
          c[1].includes('trip_1'),
      ),
    ),
  ).toBeTruthy();
});
test('request approval and author accepts applicant', async ({page}) => {
  const requests = await setup(page, 'en', 'approval');
  await open(page);
  await page.locator('#list .flt').first().click();
  await page.locator('#acts .pri').click();
  await expect(page.locator('#acts')).toContainText('Request sent');
  await page.locator('#mb .x').click();
  await page.locator('#list .flt').nth(1).click();
  await page
    .locator('#acts button')
    .filter({
      hasText: 'Requests',
    })
    .click();
  await page.locator('[data-a="8"]').click();
  await expect(page.locator('.req')).toHaveCount(0);
  expect(
    requests.some((r) => r.path === '/trips/2/requests/8/accept'),
  ).toBeTruthy();
});
test('onboarding and profile registration', async ({page}) => {
  const requests = await setup(page, 'en', 'onboarding');
  await open(page);
  await expect(page.locator('#rg')).toBeVisible();
  await page.locator('#bd0').fill('1997-01-01');
  await page.locator('#rc').fill('Madrid');
  await page.locator('#ra').fill('Hello');
  await page.locator('#gs [data-s="f"]').click();
  await page.locator('#vb [data-v="nature"]').click();
  await page.locator('input[name="rules_accepted"]').check();
  await page.locator('#rg').click();
  await expect(page.locator('.ms')).not.toHaveClass(/on/);
  expect(requests.find((r) => r.path === '/register')?.body).toMatchObject({
    birth: '1997-01-01',
    gender: 'f',
    city: 'Madrid',
    vibe: [
      'nature',
    ],
    rules_accepted: true,
  });
});
test('Stars invoice and author close action', async ({page}) => {
  const requests = await setup(page);
  await open(page);
  await page.locator('#list .flt').nth(1).click();
  await page
    .locator('#acts button')
    .filter({
      hasText: 'Boost',
    })
    .click();
  await expect(page.locator('.ms')).not.toHaveClass(/on/);
  expect(
    await page.evaluate(() =>
      window.__telegramCalls.some((c: unknown[]) => c[0] === 'invoice'),
    ),
  ).toBeTruthy();
  await page.locator('#list .flt').nth(1).click();
  await page
    .locator('#acts button')
    .filter({
      hasText: 'Close',
    })
    .click();
  expect(requests.some((r) => r.path === '/trips/2/close')).toBeTruthy();
});
test('review and edit profile', async ({page}) => {
  const requests = await setup(page, 'en', 'ended');
  await open(page, '?rate=1');
  await page.locator('#sp [data-n="5"]').click();
  await page.locator('#tgs [data-t="reliable"]').click();
  await page.locator('#rtx').fill('Great company');
  await page.locator('#go').click();
  await expect(page.locator('.ms')).not.toHaveClass(/on/);
  expect(requests.find((r) => r.path === '/reviews')?.body).toMatchObject({
    trip_id: 1,
    to_id: 8,
    stars: 5,
    tags: [
      'reliable',
    ],
    text: 'Great company',
  });
  await page.locator('#n_pass').click();
  await page.locator('#edit').click();
  await page.locator('#city').fill('Barcelona');
  await page.locator('#sv').click();
  await expect(page.locator('.who')).toContainText('Barcelona');
});
for (const query of [
  '?trip=1',
  '?chat=1',
  '?req=2',
]) {
  test(`deep link ${query}`, async ({page}) => {
    await setup(page);
    await open(page, query);
    await expect(page.locator('.ms.on')).toBeVisible();
    if (query.includes('chat')) {
      await expect(page.locator('#mi')).toBeVisible();
    }
    if (query.includes('req')) {
      await expect(page.locator('.req')).toHaveCount(1);
    }
  });
}
test('chat stops polling on close and ignores late response', async ({
                                                                       page,
                                                                     }) => {
  test.skip(
    process.env.FRONTEND_TARGET === 'legacy',
    'Legacy lifecycle bug is intentionally not an acceptance baseline',
  );
  const requests = await setup(page);
  await open(page, '?chat=1');
  await expect(page.locator('.m')).toHaveCount(1);
  let release: (() => void) | undefined;
  await page.route('**/api/trips/1/chat?since=1', async (route) => {
    await new Promise<void>((resolve) => (release = resolve));
    await route
      .fulfill({
        json: {
          dest: 'Old chat',
          me: 7,
          author_id: 7,
          ended: false,
          closed: false,
          members: [],
          messages: [
            {
              id: 2,
              user_id: 8,
              name: 'Late',
              text: 'Must not appear',
            },
          ],
          reactions: {},
        },
      })
      .catch(() => {
      });
  });
  await page.clock.runFor(4000);
  await expect.poll(() => !!release).toBe(true);
  await page.locator('#mb .x').click();
  await page.locator('#plus').click();
  release?.();
  await page.clock.runFor(12000);
  await expect(page.locator('#pub')).toBeVisible();
  await expect(page.locator('#mb')).not.toContainText('Must not appear');
  expect(requests.filter((r) => r.path === '/trips/1/chat')).toHaveLength(1);
});

test('joining state survives close and reopen', async ({page}) => {
  await setup(page);
  await open(page);
  await page.locator('#list .flt').first().click();
  await page.locator('#acts .pri').click();
  await page.locator('#mb .x').click();
  await page.locator('#list .flt').first().click();
  await expect(page.locator('#acts .pri')).toHaveCount(0);
  await expect(page.locator('#acts')).toContainText('Open chat');
});
test('pending request survives close and reopen', async ({page}) => {
  await setup(page, 'en', 'approval');
  await open(page);
  await page.locator('#list .flt').first().click();
  await page.locator('#acts .pri').click();
  await page.locator('#mb .x').click();
  await page.locator('#list .flt').first().click();
  await expect(page.locator('#acts .pri')).toHaveCount(0);
  await expect(page.locator('#acts button:disabled')).toContainText(
    'Request sent',
  );
});
