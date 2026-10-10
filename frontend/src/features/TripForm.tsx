import {createMemo, createSignal, For, onCleanup} from 'solid-js';
import {api} from '../api/client';
import {useApp} from '../app/context';
import {Choices, Close} from '../components/common';
import {CITY} from '../data/cities';
import {KIND} from '../data/trips';
import {language, tx} from '../i18n';
import {platform} from '../platform/telegram';

export function TripForm() {
  const app = useApp();
  const [kind, setKind] = createSignal('flight');
  const [audience, setAudience] = createSignal('all');
  const [query, setQuery] = createSignal('');
  const [picked, setPicked] = createSignal<(typeof CITY)[number]>();
  const [choosing, setChoosing] = createSignal(false);
  const [busy, setBusy] = createSignal(false);
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  let form!: HTMLFormElement;
  const today = new Date().toISOString().slice(0, 10);
  const suggestions = createMemo(() => {
    const q = query().trim().toLowerCase();
    return q && choosing()
      ? CITY.filter((c) =>
        [
          c.en,
          c.ru,
          c.ce,
          c.cr,
        ]
          .join(' ')
          .toLowerCase()
          .includes(q),
      )
        .sort((a, b) => Number(b.en === b.ce) - Number(a.en === a.ce))
        .slice(0, 8)
      : [];
  });
  const value = (name: string) => String(new FormData(form).get(name) || '');
  const submit = async () => {
    if (busy()) {
      return;
    }
    setBusy(true);
    await app.run(async () => {
      const typed = query().trim();
      if (!typed) {
        throw new Error(tx('nodest'));
      }
      const city =
        picked() ||
        CITY.find(
          (c) =>
            c.en.toLowerCase() === typed.toLowerCase() ||
            c.ru.toLowerCase() === typed.toLowerCase(),
        );
      await api(
        '/trips',
        'POST',
        {
          dest: city?.en || typed,
          country: city?.ce || '',
          lat: city?.lat ?? null,
          lon: city?.lon ?? null,
          kind: kind(),
          date_from: value('df'),
          date_to: value('dt'),
          people: +value('pp') || 1,
          budget: value('bd'),
          note: value('nt'),
          audience: audience(),
          min_age: +value('a1') || 0,
          max_age: +value('a2') || 0,
          approval: new FormData(form).has('ap') ? 1 : 0,
        },
        controller.signal,
      );
      platform.success();
      app.close();
      app.toast(tx('posted'));
      app.show('pass');
    });
    setBusy(false);
  };
  return (
    <form
      class="form"
      ref={form}
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Close/>
      <h2>{tx('create')}</h2>
      <label>{tx('kind')}</label>
      <div class="chips" id="kc">
        <For each={Object.keys(KIND)}>
          {(k) => (
            <button
              type="button"
              class="chip"
              data-k={k}
              aria-pressed={kind() === k}
              onClick={() => {
                setKind(k);
                platform.haptic();
              }}
            >
              {`${KIND[k]} ${tx(k)}`}
            </button>
          )}
        </For>
      </div>
      <label for="dest">{tx('where')}</label>
      <input
        class="f"
        id="dest"
        placeholder={tx('ph')}
        autocomplete="off"
        value={query()}
        onInput={(e) => {
          setQuery(e.currentTarget.value);
          setPicked();
          setChoosing(true);
        }}
      />
      <div class="opts" id="opts">
        <For each={suggestions()}>
          {(c) => (
            <button
              type="button"
              class="opt"
              onClick={() => {
                setPicked(c);
                setQuery(language() === 'ru' ? c.ru : c.en);
                setChoosing(false);
              }}
            >
              {language() === 'ru' ? c.ru : c.en}
              {c.en === c.ce ? (
                ''
              ) : (
                <>
                  {' '}
                  <span class="mu">{language() === 'ru' ? c.cr : c.ce}</span>
                </>
              )}
            </button>
          )}
        </For>
      </div>
      <div class="two">
        <div>
          <label for="df">{tx('from')}</label>
          <input class="f" id="df" name="df" type="date" min={today}/>
        </div>
        <div>
          <label for="dt">{tx('to')}</label>
          <input class="f" id="dt" name="dt" type="date" min={today}/>
        </div>
      </div>
      <div class="two">
        <div>
          <label for="pp">{tx('people')}</label>
          <input
            class="f"
            id="pp"
            name="pp"
            type="number"
            min="1"
            max="20"
            value="1"
          />
        </div>
        <div>
          <label for="bd">{tx('budget')}</label>
          <input class="f" id="bd" name="bd" placeholder="€800"/>
        </div>
      </div>
      <p class="mu text-[14px] mt-[-4px] mb-[12px]">{tx('limitnote')}</p>
      <label>{tx('who_t')}</label>
      <Choices
        id="au2"
        options={[
          'all',
          'f',
          'm',
        ].map((v) => [
          v,
          tx(`aud_${v}`),
        ])}
        selected={audience()}
        onChange={setAudience}
      />
      <label>{tx('age_t')}</label>
      <div class="two">
        <div>
          <input
            class="f"
            id="a1"
            name="a1"
            type="number"
            min="18"
            max="99"
            placeholder="18"
          />
        </div>
        <div>
          <input
            class="f"
            id="a2"
            name="a2"
            type="number"
            min="18"
            max="99"
            placeholder="99"
          />
        </div>
      </div>
      <label class="sw">
        <input type="checkbox" id="ap" name="ap"/>
        <span>
          {tx('approval')}
          <br/>
          <small class="mu">{tx('approval_h')}</small>
        </span>
      </label>
      <label for="nt">{tx('plan_l')}</label>
      <textarea class="f" id="nt" name="nt" placeholder={tx('phn')}/>
      <button type="submit" class="cta pri" id="pub" disabled={busy()}>
        {tx('publish')}
      </button>
    </form>
  );
}
