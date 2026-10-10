import {createResource, createSignal, For, onCleanup, Show} from 'solid-js';
import {api} from '../api/client';
import type {Me, MyTrips, PublicProfile} from '../api/types';
import {splitVibes} from '../api/types';
import {useApp} from '../app/context';
import {
  Choices,
  Close,
  Identity,
  Metrics,
  MultiChoices,
  VibeBadges,
} from '../components/common';
import {TripRow} from '../components/TripRow';
import {ci, dn, NEG} from '../data/trips';
import {fmt, tx} from '../i18n';
import {platform} from '../platform/telegram';

export function Passport() {
  const app = useApp();
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  const [data] = createResource(app.revision, async () => {
    let result:
      | {
      me: Me;
      trips: MyTrips;
    }
      | undefined;
    await app.run(async () => {
      const [me, trips] = await Promise.all([
        app.refreshMe(),
        api<MyTrips>('/my', 'GET', undefined, controller.signal),
      ]);
      if (!controller.signal.aborted) {
        result = {
          me,
          trips,
        };
      }
    });
    return result;
  });
  return (
    <Show when={data()} fallback={<p class="mu c">…</p>}>
      {(d) => {
        const all = () => [
          ...d().trips.mine,
          ...d().trips.joined,
        ];
        return (
          <div class="scroll">
            <Identity
              name={d().me.name}
              age={d().me.age}
              city={d().me.city}
              photo={platform.user.photo_url}
            >
              <button
                type="button"
                class="ghost"
                id="edit"
                onClick={() =>
                  app.open({
                    kind: 'edit',
                    me: d().me,
                  })
                }
              >
                {tx('edit')}
              </button>
            </Identity>
            <Show when={d().me.about}>
              <p>{d().me.about}</p>
            </Show>
            <Metrics stats={d().me}/>
            <button
              type="button"
              class="ghost w-full"
              id="pub0"
              onClick={() =>
                app.open({
                  kind: 'profile',
                  id: d().me.id,
                })
              }
            >
              {tx('myprof')}
            </button>
            <h3>{tx('stamps')}</h3>
            <Show when={all().length} fallback={<p class="mu">{tx('nost')}</p>}>
              <div class="stamps">
                <For each={all()}>
                  {(trip, index) => (
                    <button
                      type="button"
                      class={`st a${ci(trip.dest)}`}
                      data-s={index()}
                      style={{
                        '--r': `${(ci(trip.dest + index()) - 2.5) * 5}deg`,
                      }}
                      onClick={() =>
                        app.open({
                          kind: 'trip',
                          trip,
                        })
                      }
                    >
                      {dn(trip.dest)}
                      <small>{fmt(trip.date_from) || '✈'}</small>
                    </button>
                  )}
                </For>
              </div>
            </Show>
            <Show when={d().trips.mine.length}>
              <h3>{tx('mytrips')}</h3>
              <For each={d().trips.mine}>
                {(trip, index) => (
                  <TripRow
                    trip={trip}
                    index={index()}
                    onClick={() =>
                      app.open({
                        kind: 'trip',
                        trip,
                      })
                    }
                  />
                )}
              </For>
            </Show>
          </div>
        );
      }}
    </Show>
  );
}

export function Profile(props: { id: number; back?: () => void }) {
  const app = useApp();
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  const [data] = createResource(
    () => props.id,
    async (id) => {
      let result: PublicProfile | undefined;
      await app.run(async () => {
        result = await api<PublicProfile>(
          `/users/${id}`,
          'GET',
          undefined,
          controller.signal,
        );
      });
      return result;
    },
  );
  return (
    <Show when={data()}>
      {(p) => (
        <div class="form">
          <Close/>
          <Show when={props.back}>
            <button type="button" class="ghost" id="bk" onClick={props.back}>
              ←
            </button>
          </Show>
          <div class="mt-[12px]">
            <Identity name={p().name} age={p().age} city={p().city}/>
          </div>
          <Metrics stats={p()}/>
          <Show when={p().about}>
            <p>{p().about}</p>
          </Show>
          <Show when={p().vibe.length}>
            <div class="mt-[6px]">
              <VibeBadges values={p().vibe}/>
            </div>
          </Show>
          <Show when={Object.keys(p().tags).length}>
            <div>
              <For each={Object.entries(p().tags).sort((a, b) => b[1] - a[1])}>
                {([key, n]) => (
                  <span class={`tgp${NEG.has(key) ? ' neg' : ''}`}>
                    {tx(`tag_${key}`)} ×{n}
                  </span>
                )}
              </For>
            </div>
          </Show>
          <h3 class="mt-[16px] mb-[8px] text-[18px]">{tx('reviews')}</h3>
          <For
            each={p().reviews}
            fallback={<p class="mu">{tx('noreviews')}</p>}
          >
            {(review) => (
              <div class="rev">
                <b class="rt">{'★'.repeat(review.stars)}</b>{' '}
                <small>
                  {review.name} · {dn(review.dest)}
                </small>
                <Show when={review.tags.length}>
                  <div>
                    <For each={review.tags}>
                      {(key) => (
                        <span class={`tgp${NEG.has(key) ? ' neg' : ''}`}>
                          {tx(`tag_${key}`)}
                        </span>
                      )}
                    </For>
                  </div>
                </Show>
                <Show when={review.text}>
                  <p>{review.text}</p>
                </Show>
              </div>
            )}
          </For>
          <Show when={!p().me}>
            <div class="two bt">
              <button
                type="button"
                class="ghost"
                id="bl"
                onClick={() => {
                  const go = () =>
                    app.run(async () => {
                      await api(
                        '/block',
                        'POST',
                        {
                          user_id: props.id,
                          on: !p().blocked,
                        },
                        controller.signal,
                      );
                      platform.success();
                      app.close();
                      app.toast(tx('done_ok'));
                      app.refresh();
                    });
                  if (p().blocked) {
                    go();
                  } else {
                    platform.confirm(tx('q_block'), go);
                  }
                }}
              >
                {tx(p().blocked ? 'unblock' : 'block')}
              </button>
              <button
                type="button"
                class="ghost"
                id="rpu"
                onClick={() =>
                  app.run(async () => {
                    await api(
                      `/users/${props.id}/report`,
                      'POST',
                      undefined,
                      controller.signal,
                    );
                    app.toast(tx('reported'));
                  })
                }
              >
                {tx('reportu')}
              </button>
            </div>
          </Show>
        </div>
      )}
    </Show>
  );
}

export function ProfileForm(props: { me?: Me }) {
  const app = useApp();
  const [gender, setGender] = createSignal('x');
  const [vibes, setVibes] = createSignal(splitVibes(props.me?.vibe));
  const [busy, setBusy] = createSignal(false);
  let form!: HTMLFormElement;
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  const value = (key: string) => String(new FormData(form).get(key) || '');

  async function save() {
    if (busy()) {
      return;
    }
    setBusy(true);
    await app.run(async () => {
      const fields = {
        city: value('city'),
        about: value('about'),
        vibe: vibes(),
      };
      if (props.me) {
        await api('/profile', 'POST', fields, controller.signal);
      } else {
        if (!value('birth')) {
          throw new Error('baddate');
        }
        await api(
          '/register',
          'POST',
          {
            ...fields,
            birth: value('birth'),
            gender: gender(),
          },
          controller.signal,
        );
      }
      await app.refreshMe();
      platform.success();
      app.close();
      app.toast(tx(props.me ? 'saved' : 'welcome'));
      app.refresh();
    });
    setBusy(false);
  }

  return (
    <form
      class="form"
      ref={form}
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
    >
      <Show when={props.me} fallback={<div class="big">🪪</div>}>
        <Close/>
      </Show>
      <h2>{props.me ? props.me.name : tx('reg_t')}</h2>
      <Show when={!props.me}>
        <p class="mu mb-[12px]">{tx('reg_p')}</p>
        <label for="bd0">{tx('birth')}</label>
        <input
          class="f"
          id="bd0"
          name="birth"
          type="date"
          min="1920-01-01"
          max={new Date().toISOString().slice(0, 10)}
        />
        <label>{tx('gender')}</label>
        <Choices
          id="gs"
          options={[
            'f',
            'm',
            'x',
          ].map((v) => [
            v,
            tx(`g_${v}`),
          ])}
          selected={gender()}
          onChange={setGender}
        />
      </Show>
      <label for={props.me ? 'city' : 'rc'}>{tx('city')}</label>
      <input
        class="f"
        id={props.me ? 'city' : 'rc'}
        name="city"
        maxlength="60"
        value={props.me?.city || ''}
      />
      <label for={props.me ? 'ab' : 'ra'}>{tx('about')}</label>
      <textarea
        class="f"
        id={props.me ? 'ab' : 'ra'}
        name="about"
        maxlength="500"
        placeholder={tx('pha')}
      >
        {props.me?.about || ''}
      </textarea>
      <label>{tx('vibe_t')}</label>
      <Show when={!props.me}>
        <p class="mu text-[13px] mt-[-2px] mb-[6px]">{tx('vibe_h')}</p>
      </Show>
      <MultiChoices id="vb" values={vibes()} onChange={setVibes}/>
      <button
        type="submit"
        class="cta"
        id={props.me ? 'sv' : 'rg'}
        disabled={busy()}
      >
        {tx(props.me ? 'save' : 'reg_go')}
      </button>
    </form>
  );
}
