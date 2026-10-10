import {expect, test} from '@playwright/test';
import {open, setup, shot} from './fixtures';

for (const language of [
  'en',
  'ru',
]) {
  for (const width of [
    390,
    360,
  ]) {
    test(`${language} ${width}: screen parity`, async ({
                                                         page,
                                                         browserName,
                                                       }) => {
      await page.setViewportSize({
        width,
        height: width === 390 ? 844 : 800,
      });
      await setup(page, language);
      await open(page, '', true);
      const prefix = `${language}-${width}`;
      const snap = async (name: string) => {
        if (browserName === 'chromium') {
          await shot(page, `${prefix}-${name}`);
        }
      };
      await snap('splash');
      await page.locator('#splash h1').click();
      await page.clock.runFor(3000);
      await expect(page.locator('#list .flt')).toHaveCount(2);
      await snap('board');
      await page.locator('#list .flt').first().click();
      await snap('trip');
      await page.locator('#au').click();
      await expect(page.locator('.rev')).toHaveCount(1);
      await snap('profile');
      await page.locator('#mb .x').click();
      await page.locator('#plus').click();
      await snap('create');
      await page.locator('#mb .x').click();
      await page.locator('#n_places').click();
      await expect(page.locator('.pc')).toHaveCount(28);
      await snap('places');
      await page.locator('#n_chat').click();
      await expect(page.locator('.scroll .flt')).toHaveCount(2);
      await snap('chats');
      await page.locator('.scroll .flt').first().click();
      await expect(page.locator('.m')).toHaveCount(1);
      await snap('chat');
      await page.locator('#cm').click();
      await snap('members');
      await page.locator('#mb .x').click();
      await page.locator('#rl').click();
      await snap('rules');
      await page.locator('#nx').click();
      await page.locator('#n_pass').click();
      await expect(page.locator('#edit')).toBeVisible();
      await snap('passport');
      await page.locator('.scroll .flt').first().click();
      await page
        .locator('#acts button')
        .filter({
          hasText: language === 'ru' ? 'Заявки' : 'Requests',
        })
        .click();
      await expect(page.locator('.req')).toHaveCount(1);
      await snap('requests');
    });
  }
}
for (const scenario of [
  'empty',
  'onboarding',
  'registration',
  'minor',
  'error',
  'full',
] as const) {
  test(`state ${scenario}`, async ({page, browserName}) => {
    await page.setViewportSize({
      width: 390,
      height: 844,
    });
    await setup(page, 'en', scenario);
    await open(page);
    if (scenario === 'full') {
      await page.locator('#list .flt').first().click();
    }
    if (scenario === 'empty') {
      await expect(page.locator('.empty')).toBeVisible();
    }
    if (
      scenario === 'onboarding' ||
      scenario === 'registration' ||
      scenario === 'minor'
    ) {
      await expect(page.locator('.ms.on')).toBeVisible();
    }
    if (scenario === 'error') {
      await page.locator('#n_board').click();
      await expect(page.locator('.toast')).toBeVisible();
    }
    if (browserName === 'chromium') {
      await shot(page, `state-${scenario}`);
    }
  });
}
for (const language of [
  'de',
  'fr',
  'it',
  'zh',
]) {
  test(`language ${language} desktop`, async ({page, browserName}) => {
    await page.setViewportSize({
      width: 1280,
      height: 800,
    });
    await setup(page, language);
    await open(page);
    await page.locator('#plus').click();
    if (browserName === 'chromium') {
      await shot(page, `${language}-desktop-create`);
    }
    await page.locator('#mb .x').click();
    await page.locator('#lang').click();
    await page.locator('#mb [data-l="en"]').click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  });
}
test('review deep link', async ({page, browserName}) => {
  await page.setViewportSize({
    width: 390,
    height: 844,
  });
  await setup(page, 'en', 'ended');
  await open(page, '?rate=1');
  await expect(page.locator('#sp')).toBeVisible();
  if (browserName === 'chromium') {
    await shot(page, 'review');
  }
});
