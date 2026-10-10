import {createSignal, For, Show} from 'solid-js';
import {api} from '../api/client';
import {useApp} from '../app/context';
import {Close} from '../components/common';
import {language, T, tx} from '../i18n';
import {platform} from '../platform/telegram';

export function Rules() {
  const app = useApp();
  return (
    <div class="form ob">
      <Close/>
      <div class="big">📜</div>
      <h2>{tx('rulesT')}</h2>
      <ul class="rules">
        <For each={T[language()].rules}>{(rule) => <li>{rule}</li>}</For>
      </ul>
      <button type="button" class="cta" id="nx" onClick={app.close}>
        {tx('ok')}
      </button>
    </div>
  );
}

export function Onboarding(props: { must: boolean }) {
  const app = useApp();
  const [step, setStep] = createSignal(0);
  const slides = () => T[language()].ob;
  const last = () => step() === slides().length;

  async function next() {
    if (!last()) {
      setStep(step() + 1);
      platform.haptic();
      return;
    }
    if (!props.must) {
      app.close();
      return;
    }
    await app.run(async () => {
      await api('/rules', 'POST');
      platform.success();
      const me = await app.refreshMe();
      if (!me.registered) {
        app.open({
          kind: 'register',
        });
      } else {
        app.close();
      }
      app.refresh();
    });
  }

  return (
    <div class="form ob">
      <Show when={!props.must}>
        <Close/>
      </Show>
      <Show
        when={last()}
        fallback={
          <>
            <div class="big">{slides()[step()].e}</div>
            <h2>{slides()[step()].h}</h2>
            <p>{slides()[step()].p}</p>
            <Show when={slides()[step()].ex}>
              <div class="ex">{slides()[step()].ex}</div>
            </Show>
          </>
        }
      >
        <div class="big">📜</div>
        <h2>{tx('rulesT')}</h2>
        <ul class="rules">
          <For each={T[language()].rules}>{(rule) => <li>{rule}</li>}</For>
        </ul>
      </Show>
      <div class="dots">
        <For
          each={Array.from(
            {
              length: slides().length + 1,
            },
            (_, i) => i,
          )}
        >
          {(index) => <i class={index === step() ? 'on' : ''}/>}
        </For>
      </div>
      <button type="button" class="cta" id="nx" onClick={next}>
        {last() ? (props.must ? tx('accept') : tx('ok')) : tx('next')}
      </button>
    </div>
  );
}

export function Minor() {
  return (
    <div class="form c">
      <div class="big">🔞</div>
      <h2>{tx('minor_t')}</h2>
      <p>{tx('minor_p')}</p>
    </div>
  );
}
