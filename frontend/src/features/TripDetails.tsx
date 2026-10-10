import {
  createMemo,
  createResource,
  createSignal,
  For,
  onCleanup,
  Show,
} from 'solid-js';
import {api} from '../api/client';
import type {Trip} from '../api/types';
import {splitVibes} from '../api/types';
import {useApp} from '../app/context';
import {Close, VibeBadges} from '../components/common';
import {WorldMap} from '../components/WorldMap';
import {big, photo} from '../data/photo';
import {byEn, ci, dn, pinCoord, range} from '../data/trips';
import {tx} from '../i18n';
import {platform} from '../platform/telegram';

export function TripDetails(props: { trip: Trip }) {
  const app = useApp();
  const [trip, setTrip] = createSignal(props.trip);
  const [joined, setJoined] = createSignal(false);
  let timer: ReturnType<typeof setTimeout> | undefined;
  const controller = new AbortController();
  onCleanup(() => {
    controller.abort();
    clearTimeout(timer);
  });
  const [image] = createResource(
    () => trip().dest,
    (dest) => photo(dest, controller.signal),
  );
  const left = () => Math.max(0, trip().people - (trip().members || 0));
  const coordinate = () => pinCoord(trip());
  const badges = () => {
    const x = trip();
    const b: string[] = [];
    if (x.audience === 'f') {
      b.push(`♀ ${tx('for_f')}`);
    }
    if (x.audience === 'm') {
      b.push(`♂ ${tx('for_m')}`);
    }
    if (x.min_age || x.max_age) {
      b.push(`${x.min_age || 18}–${x.max_age || '∞'} ${tx('yo')}`);
    }
    if (x.approval) {
      b.push(`📩 ${tx('byreq')}`);
    }
    return b;
  };
  const match = () =>
    splitVibes(trip().a_vibe).filter((v) =>
      splitVibes(app.me()?.vibe).includes(v),
    ).length;
  const action = (fn: () => Promise<unknown>) => () => app.run(fn);
  const actions = createMemo(() => {
    const x = trip();
    const result: {
      text: string;
      fn?: () => void;
      alt?: boolean;
      disabled?: boolean;
      primary?: boolean;
    }[] = [];
    const add = (text: string, fn?: () => void, flags = {}) =>
      result.push({
        text,
        fn,
        ...flags,
      });
    if (x.mine || x.joined) {
      if (x.chat_open) {
        add(tx('openchat'), () =>
          app.open({
            kind: 'chat',
            id: x.id,
          }),
        );
      } else {
        add(`${tx('waiting')}: ${x.members || 0}/${x.people}`, undefined, {
          disabled: true,
        });
      }
      if (x.ended && (x.to_rate || 0) > 0) {
        add(
          `⭐ ${tx('rate')}`,
          () =>
            app.open({
              kind: 'rate',
              id: x.id,
            }),
          {
            alt: true,
          },
        );
      }
      if (x.mine && x.pending > 0) {
        add(`📩 ${tx('reqs_t')} (${x.pending})`, () =>
          app.open({
            kind: 'requests',
            trip: x,
          }),
        );
      }
      if (x.mine && !x.ended && !x.closed) {
        add(
          tx('boost'),
          action(async () => {
            const {link} = await api<{
              link: string;
            }>(`/trips/${x.id}/boost`, 'POST');
            if (controller.signal.aborted) {
              return;
            }
            platform.invoice(link, (status) => {
              if (status === 'paid' && !controller.signal.aborted) {
                platform.success();
                app.close();
                app.toast(tx('boosted'));
                app.refresh();
              }
            });
          }),
          {
            alt: true,
          },
        );
        add(
          tx('close'),
          () =>
            platform.confirm(
              tx('q_close'),
              action(async () => {
                await api(
                  `/trips/${x.id}/close`,
                  'POST',
                  undefined,
                  controller.signal,
                );
                platform.success();
                app.close();
                app.toast(tx('closedt'));
                app.refresh();
              }),
            ),
          {
            alt: true,
          },
        );
      }
    } else {
      if (x.ended) {
        add(tx('ended_t'), undefined, {
          disabled: true,
        });
      } else if (x.closed) {
        add(tx('closedt'), undefined, {
          disabled: true,
        });
      } else if (left() <= 0) {
        add(tx('fullt'), undefined, {
          disabled: true,
        });
      } else if (x.req === 'pending') {
        add(tx('req_pend'), undefined, {
          disabled: true,
        });
      } else if (x.req === 'declined') {
        add(tx('err_declined'), undefined, {
          disabled: true,
        });
      } else {
        add(
          x.approval ? tx('req_send') : tx('join'),
          action(async () => {
            const r = await api<{
              pending?: boolean;
            }>(`/trips/${x.id}/join`, 'POST', undefined, controller.signal);
            if (r.pending) {
              const updated = {
                ...x,
                req: 'pending',
              };
              setTrip(updated);
              app.setList(
                app.list().map((item) => (item.id === x.id ? updated : item)),
              );
              platform.success();
              app.toast(tx('req_sent'));
              return;
            }
            const updated = {
              ...x,
              joined: 1,
              members: (x.members || 0) + 1,
              chat_open: 1,
            };
            setTrip(updated);
            app.setList(
              app.list().map((item) => (item.id === x.id ? updated : item)),
            );
            setJoined(true);
            platform.success();
            app.toast(tx('chatopen'));
            timer = setTimeout(
              () =>
                app.open({
                  kind: 'chat',
                  id: x.id,
                }),
              1800,
            );
          }),
          {
            primary: true,
          },
        );
      }
    }
    add(`🔗 ${tx('share')}`, () => app.share(x), {
      alt: true,
    });
    return result;
  });
  return (
    <div class="pass">
      <Close/>
      <div
        class={`pt a${ci(trip().dest)}${image() ? ' ph' : ''}`}
        style={{
          'background-image': image()
            ? `linear-gradient(180deg,#0B1B3F55,#0B1B3Fd9),url("${big(image() || '', 960)}")`
            : undefined,
        }}
      >
        <div class="mini">Travel Friends · {tx('pass')}</div>
        <h2>{dn(trip().dest)}</h2>
        <div class="grid">
          <div>
            <small>{tx('who')}</small>
            <b>
              <button
                type="button"
                class="lnk"
                id="au"
                onClick={() =>
                  app.open({
                    kind: 'profile',
                    id: trip().author_id || trip().user_id,
                    back: () =>
                      app.open({
                        kind: 'trip',
                        trip: trip(),
                      }),
                  })
                }
              >
                {trip().name}
              </button>
              {trip().age ? `, ${trip().age}` : ''}
            </b>
            <small>
              {trip().a_cnt
                ? `★ ${trip().a_avg} (${trip().a_cnt})`
                : tx('newbie')}
            </small>
          </div>
          <div>
            <small>{tx('when')}</small>
            <b>{range(trip())}</b>
          </div>
          <div>
            <small>{tx('seats')}</small>
            <b>
              {left()} / {trip().people}
            </b>
          </div>
          <div>
            <small>{tx('budget')}</small>
            <b>{trip().budget || '—'}</b>
          </div>
        </div>
      </div>
      <div class="tearl"/>
      <div class={`stub${joined() ? ' torn' : ''}`}>
        <Show when={trip().note}>
          <p>{trip().note}</p>
        </Show>
        <Show when={trip().about}>
          <p class="mu">
            {trip().name}
            {trip().city ? `, ${trip().city}` : ''}: {trip().about}
          </p>
        </Show>
        <p>
          <For each={badges()}>
            {(badge) => <span class="badge">{badge}</span>}
          </For>
        </p>
        <Show when={splitVibes(trip().a_vibe).length}>
          <p>
            <VibeBadges values={splitVibes(trip().a_vibe)}/>
          </p>
        </Show>
        <Show when={!trip().mine && match()}>
          <span class="match">
            ✨ {tx('match').replace('{n}', String(match()))}
          </span>
        </Show>
        <div class="mm" id="mm" hidden={!coordinate()}>
          <Show when={coordinate()}>
            {(c) => (
              <WorldMap
                coordinate={c()}
                country={byEn[trip().dest]?.en === byEn[trip().dest]?.ce}
              />
            )}
          </Show>
        </div>
        <div class="bar"/>
        <div id="acts">
          <For each={actions()}>
            {(a) => (
              <button
                type="button"
                class={`cta${a.alt ? ' alt' : a.primary ? ' pri' : ''}`}
                disabled={a.disabled}
                onClick={a.fn}
              >
                {a.text}
              </button>
            )}
          </For>
        </div>
      </div>
      <Show when={joined()}>
        <div class="stamp">{tx('going')}</div>
      </Show>
    </div>
  );
}
