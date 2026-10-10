import {createResource, For, onCleanup, Show} from 'solid-js';
import {api} from '../api/client';
import type {MyTrips} from '../api/types';
import {useApp} from '../app/context';
import {TripRow} from '../components/TripRow';
import {tx} from '../i18n';

export function ChatList() {
  const app = useApp();
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  const [data] = createResource(app.revision, async () => {
    let result: MyTrips | undefined;
    await app.run(async () => {
      result = await api<MyTrips>('/my', 'GET', undefined, controller.signal);
    });
    return result;
  });
  const trips = () => [
    ...(data()?.mine || []).filter((x) => x.chat_open || x.members > 0),
    ...(data()?.joined || []),
  ];
  return (
    <Show when={data()} fallback={<p class="mu c">…</p>}>
      <div class="scroll">
        <div class="two bt">
          <button
            type="button"
            class="ghost"
            id="hw"
            onClick={() =>
              app.open({
                kind: 'onboarding',
                must: false,
              })
            }
          >
            {tx('howto')}
          </button>
          <button
            type="button"
            class="ghost"
            id="rl"
            onClick={() =>
              app.open({
                kind: 'rules',
              })
            }
          >
            {tx('rulesT')}
          </button>
        </div>
        <h3>{tx('mychats')}</h3>
        <For each={trips()} fallback={<p class="mu">{tx('nochats')}</p>}>
          {(trip, index) => (
            <TripRow
              trip={trip}
              index={index()}
              onClick={() =>
                app.open(
                  trip.chat_open
                    ? {
                      kind: 'chat',
                      id: trip.id,
                    }
                    : {
                      kind: 'trip',
                      trip,
                    },
                )
              }
            />
          )}
        </For>
      </div>
    </Show>
  );
}
