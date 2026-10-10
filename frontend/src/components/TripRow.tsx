import {Show} from 'solid-js';
import type {Trip} from '../api/types';
import {ci, dn, ke} from '../data/trips';
import {loc, tx} from '../i18n';

export function TripRow(props: {
  trip: Trip;
  index: number;
  onClick: () => void;
}) {
  const date = () =>
    props.trip.date_from ? new Date(props.trip.date_from) : null;
  const tag = () => {
    const x = props.trip;
    return x.pending > 0
      ? `📩 ${x.pending}`
      : x.req === 'pending'
        ? '⏳'
        : (x.members || 0) >= x.people
          ? tx('fullt')
          : x.closed
            ? tx('closedt')
            : (x.to_rate || 0) > 0
              ? `⭐ ${tx('torate')}`
              : x.boosted
                ? tx('boarding')
                : Date.now() / 1000 - x.created < 172800
                  ? tx('isnew')
                  : '';
  };
  return (
    <button
      type="button"
      class={`flt a${ci(props.trip.dest)}`}
      data-i={props.index}
      style={{
        '--d': `${Math.min(props.index, 12) * 45}ms`,
      }}
      onClick={props.onClick}
    >
      <div class="dt">
        <b>{date() ? date()?.getDate() : ke(props.trip)}</b>
        <span>
          {date()
            ? date()
              ?.toLocaleDateString(loc(), {
                month: 'short',
              })
              .replace('.', '')
            : ''}
        </span>
      </div>
      <div class="mid">
        <h3>
          {ke(props.trip)} {dn(props.trip.dest)}
        </h3>
        <p>
          <Show when={tag()}>
            <span class="tag">{tag()}</span>
          </Show>
          {props.trip.name}
          {props.trip.age ? `, ${props.trip.age}` : ''} ·{' '}
          {props.trip.a_cnt ? `★${props.trip.a_avg}` : tx('newbie')}
        </p>
      </div>
      <div class="seat">
        <b>{Math.max(0, props.trip.people - (props.trip.members || 0))}</b>
        <span>{tx('left')}</span>
      </div>
    </button>
  );
}
