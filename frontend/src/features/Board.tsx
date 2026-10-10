import {createMemo, createResource, For, onCleanup, Show} from 'solid-js';
import {api} from '../api/client';
import type {Trip} from '../api/types';
import {useApp} from '../app/context';
import {TripRow} from '../components/TripRow';
import {WorldMap} from '../components/WorldMap';
import {dn, filterTrips, KIND} from '../data/trips';
import {tx} from '../i18n';
import {platform} from '../platform/telegram';

export function Board() {
  const app = useApp();
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  const [loaded] = createResource(app.revision, async () => {
    let success = false;
    await app.run(async () => {
      app.setList(
        await api<Trip[]>('/trips', 'GET', undefined, controller.signal),
      );
      success = true;
    });
    return success;
  });
  const base = createMemo(() =>
    filterTrips(app.list(), app.query(), app.kind()),
  );
  const visible = createMemo(() =>
    base().filter((x) => !app.place() || x.dest === app.place()),
  );
  return (
    <>
      <input
        class="q"
        id="q"
        type="search"
        placeholder={tx('search')}
        value={app.query()}
        onInput={(e) => {
          app.setQuery(e.currentTarget.value);
          app.setPlace('');
        }}
      />
      <div class="chips" id="chips">
        <For
          each={[
            'all',
            ...Object.keys(KIND),
          ]}
        >
          {(kind) => (
            <button
              type="button"
              class="chip"
              data-k={kind}
              aria-pressed={kind === app.kind()}
              onClick={() => {
                app.setKind(kind);
                app.setPlace('');
                platform.haptic();
                app.refresh();
              }}
            >
              {(kind === 'all' ? '' : `${KIND[kind]} `) + tx(kind)}
            </button>
          )}
        </For>
      </div>
      <div class="map" id="map">
        <WorldMap
          trips={base()}
          selected={app.place()}
          onSelect={app.setPlace}
        />
      </div>
      <div class="mh">
        <b id="mc">
          <Show when={loaded()}>
            {app.place() ? `${dn(app.place())} · ` : '🌍 '}
            {tx('trips_cnt').replace('{n}', String(visible().length))}
          </Show>
        </b>
        <button
          type="button"
          class="ghost sm"
          id="mclr"
          hidden={!app.place()}
          onClick={() => {
            app.setPlace('');
            platform.haptic();
          }}
        >
          {' '}
          {tx('showall')}
        </button>
      </div>
      <div class="list" id="list">
        <For
          each={visible()}
          fallback={
            <Show when={loaded()}>
              <div class="empty">
                <h2>{tx('e1')}</h2>
                <p class="mu">{tx('e2')}</p>
              </div>
            </Show>
          }
        >
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
      </div>
    </>
  );
}
