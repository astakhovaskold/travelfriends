import {
  createMemo,
  createResource,
  createSignal,
  For,
  onCleanup,
} from 'solid-js';
import {api} from '../api/client';
import type {Trip} from '../api/types';
import {useApp} from '../app/context';
import {CITY} from '../data/cities';
import {big, photo} from '../data/photo';
import {POPD} from '../data/popular';
import {ci, dn} from '../data/trips';
import {tx} from '../i18n';
import {platform} from '../platform/telegram';

function PlaceCard(props: {
  dest: string;
  count: number;
  onClick: () => void;
}) {
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  const [image] = createResource(
    () => props.dest,
    (dest) => photo(dest, controller.signal),
  );
  return (
    <button
      type="button"
      class={`pc a${ci(props.dest)}`}
      data-d={props.dest}
      onClick={props.onClick}
    >
      <div
        class="pi"
        style={{
          'background-image': image()
            ? `url("${big(image() || '', 500)}")`
            : undefined,
        }}
      />
      <b>{dn(props.dest)}</b>
      <span>{tx('trips_cnt').replace('{n}', String(props.count))}</span>
    </button>
  );
}

export function Places() {
  const app = useApp();
  const [query, setQuery] = createSignal('');
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  createResource(app.revision, async () =>
    app.run(async () =>
      app.setList(
        await api<Trip[]>('/trips', 'GET', undefined, controller.signal),
      ),
    ),
  );
  const destinations = createMemo(() => {
    const q = query().trim().toLowerCase();
    return q
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
        .slice(0, 30)
        .map((c) => c.en)
      : POPD;
  });
  return (
    <>
      <input
        class="q"
        id="pq"
        type="search"
        placeholder={tx('search')}
        onInput={(e) => setQuery(e.currentTarget.value)}
      />
      <div class="scroll">
        <h3 class="mt-[2px]">{tx('popt')}</h3>
        <div class="pgrid" id="pg">
          <For each={destinations()}>
            {(dest) => (
              <PlaceCard
                dest={dest}
                count={app.list().filter((x) => x.dest === dest).length}
                onClick={() => {
                  app.setQuery(dn(dest));
                  app.setKind('all');
                  app.setPlace('');
                  platform.haptic();
                  app.show('board');
                }}
              />
            )}
          </For>
        </div>
        <p class="mu text-[12px] mt-[14px]">{tx('photoby')}</p>
      </div>
    </>
  );
}
