import {createResource, createSignal, For, onCleanup, Show} from 'solid-js';
import {api} from '../api/client';
import type {People} from '../api/types';
import {useApp} from '../app/context';
import {Close, MultiChoices} from '../components/common';
import {dn, TAGS} from '../data/trips';
import {tx} from '../i18n';
import {platform} from '../platform/telegram';

export function Review(props: { id: number; only?: number }) {
  const app = useApp();
  const [index, setIndex] = createSignal(0);
  const [stars, setStars] = createSignal(0);
  const [tags, setTags] = createSignal<string[]>([]);
  const [text, setText] = createSignal('');
  const [busy, setBusy] = createSignal(false);
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  const [data] = createResource(async () => {
    let result: People | undefined;
    await app.run(async () => {
      result = await api<People>(
        `/trips/${props.id}/people`,
        'GET',
        undefined,
        controller.signal,
      );
      if (!result.ended) {
        throw new Error('notended');
      }
      if (
        !result.members.some(
          (m) =>
            m.id !== result?.me &&
            !m.rated &&
            (!props.only || m.id === props.only),
        )
      ) {
        app.toast(tx('norate'));
        app.close();
      }
    });
    return result;
  });
  const queue = () =>
    data()?.members.filter(
      (m) =>
        m.id !== data()?.me && !m.rated && (!props.only || m.id === props.only),
    ) || [];
  const person = () => queue()[index()];

  function next() {
    if (index() + 1 >= queue().length) {
      app.close();
      app.toast(tx('rated_ok'));
      app.refresh();
      return;
    }
    setIndex(index() + 1);
    setStars(0);
    setTags([]);
    setText('');
  }

  async function send() {
    if (!stars()) {
      platform.haptic();
      app.toast(tx('pickstars'));
      return;
    }
    if (busy()) {
      return;
    }
    setBusy(true);
    await app.run(async () => {
      await api(
        '/reviews',
        'POST',
        {
          trip_id: props.id,
          to_id: person().id,
          stars: stars(),
          tags: tags(),
          text: text(),
        },
        controller.signal,
      );
      platform.success();
      next();
    });
    setBusy(false);
  }

  return (
    <Show when={person()}>
      {(member) => (
        <div class="form">
          <Close/>
          <h2>{tx('rate_t')}</h2>
          <p class="mu">{dn(data()?.dest || '')}</p>
          <h3 class="mt-[10px] text-[20px]">
            {member().name}
            {member().age ? `, ${member().age}` : ''}
          </h3>
          <div class="sp" id="sp">
            <For
              each={[
                1,
                2,
                3,
                4,
                5,
              ]}
            >
              {(n) => (
                <button
                  type="button"
                  data-n={n}
                  aria-label={String(n)}
                  class={n <= stars() ? 'on' : ''}
                  onClick={() => {
                    setStars(n);
                    platform.haptic();
                  }}
                >
                  ★
                </button>
              )}
            </For>
          </div>
          <MultiChoices
            id="tgs"
            options={TAGS}
            prefix="tag_"
            values={tags()}
            onChange={setTags}
          />
          <textarea
            class="f"
            id="rtx"
            maxlength="300"
            placeholder={tx('rate_ph')}
            value={text()}
            onInput={(e) => setText(e.currentTarget.value)}
          />
          <button
            type="button"
            class="cta"
            id="go"
            disabled={busy()}
            onClick={send}
          >
            {tx('rate_send')}
          </button>
          <button type="button" class="cta alt" id="sk" onClick={next}>
            {tx('rate_skip')}
          </button>
        </div>
      )}
    </Show>
  );
}
