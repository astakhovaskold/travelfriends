import {createResource, For, onCleanup} from 'solid-js';
import {api} from '../api/client';
import type {Member, Trip} from '../api/types';
import {useApp} from '../app/context';
import {Close} from '../components/common';
import {dn} from '../data/trips';
import {tx} from '../i18n';
import {platform} from '../platform/telegram';

export function Requests(props: { trip: Trip }) {
  const app = useApp();
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  const [requests, {refetch}] = createResource(async () => {
    let result: Member[] = [];
    await app.run(async () => {
      result = await api<Member[]>(
        `/trips/${props.trip.id}/requests`,
        'GET',
        undefined,
        controller.signal,
      );
    });
    return result;
  });
  const answer = (member: Member, action: string) =>
    app.run(async () => {
      await api(
        `/trips/${props.trip.id}/requests/${member.id}/${action}`,
        'POST',
        undefined,
        controller.signal,
      );
      platform.success();
      await refetch();
      app.refresh();
    });
  return (
    <div class="form">
      <Close/>
      <h2>{tx('reqs_t')}</h2>
      <p class="mu">{dn(props.trip.dest)}</p>
      <For each={requests()} fallback={<p class="mu">{tx('noreqs')}</p>}>
        {(member) => (
          <div class="req">
            <div class="mid">
              <button
                type="button"
                class="lnk"
                data-p={member.id}
                onClick={() =>
                  app.open({
                    kind: 'profile',
                    id: member.id,
                    back: () =>
                      app.open({
                        kind: 'requests',
                        trip: props.trip,
                      }),
                  })
                }
              >
                {member.name}
              </button>
              {member.age ? `, ${member.age}` : ''}
              <p>
                {member.a_cnt
                  ? `★ ${member.a_avg} (${member.a_cnt})`
                  : tx('newbie')}
              </p>
            </div>
            <button
              type="button"
              class="ghost sm ok"
              data-a={member.id}
              onClick={() => answer(member, 'accept')}
            >
              {tx('acc')}
            </button>
            <button
              type="button"
              class="ghost sm"
              data-d={member.id}
              onClick={() => answer(member, 'decline')}
            >
              {tx('dec')}
            </button>
          </div>
        )}
      </For>
    </div>
  );
}
