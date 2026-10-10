import {For, type JSX} from 'solid-js';
import type {Stats} from '../api/types';
import {useApp} from '../app/context';
import {VIBES, yo} from '../data/trips';
import {tx} from '../i18n';
import {platform} from '../platform/telegram';

export function Close() {
  const app = useApp();
  return (
    <button type="button" class="x" aria-label="Close" onClick={app.close}>
      ✕
    </button>
  );
}

export function Metrics(props: { stats: Stats }) {
  return (
    <div class="metrics">
      <div>
        <b>{props.stats.trips}</b>
        <span>{tx('trips_done')}</span>
      </div>
      <div>
        <b>{props.stats.friends || 0}</b>
        <span>{tx('friends')}</span>
      </div>
      <div>
        <b>{props.stats.cnt ? `★ ${props.stats.avg}` : '—'}</b>
        <span>
          {tx('rating')}
          {props.stats.cnt ? ` (${props.stats.cnt})` : ''}
        </span>
      </div>
    </div>
  );
}

export function Identity(props: {
  name: string;
  age: number | null;
  city: string;
  photo?: string;
  children?: JSX.Element;
}) {
  return (
    <div class="who">
      <div class="ava">
        {props.photo ? (
          <img src={props.photo} alt=""/>
        ) : (
          (props.name || '?')[0]
        )}
      </div>
      <div>
        <h2>{props.name}</h2>
        <p class="mu">
          {[
            yo(props.age),
            props.city || '',
          ]
            .filter(Boolean)
            .join(' · ')}
        </p>
      </div>
      {props.children}
    </div>
  );
}

export function VibeBadges(props: { values: string[] }) {
  return (
    <For each={props.values}>
      {(value) => <span class="badge">{tx(`v_${value}`)}</span>}
    </For>
  );
}

export function Choices(props: {
  id?: string;
  class?: string;
  options: [
    string,
    string,
  ][];
  selected: string;
  onChange: (value: string) => void;
}) {
  return (
    <div id={props.id} class={props.class || 'seg'}>
      <For each={props.options}>
        {([value, text]) => (
          <button
            type="button"
            class="chip"
            data-s={value}
            aria-pressed={props.selected === value}
            onClick={() => {
              platform.haptic();
              props.onChange(value);
            }}
          >
            {text}
          </button>
        )}
      </For>
    </div>
  );
}

export function MultiChoices(props: {
  id?: string;
  values: string[];
  options?: string[];
  prefix?: string;
  onChange: (values: string[]) => void;
}) {
  return (
    <div id={props.id} class="chips wrap">
      <For each={props.options || VIBES}>
        {(value) => (
          <button
            type="button"
            class="chip"
            data-v={value}
            data-t={value}
            aria-pressed={props.values.includes(value)}
            onClick={() => {
              platform.haptic();
              props.onChange(
                props.values.includes(value)
                  ? props.values.filter((v) => v !== value)
                  : [
                    ...props.values,
                    value,
                  ],
              );
            }}
          >
            {tx((props.prefix || 'v_') + value)}
          </button>
        )}
      </For>
    </div>
  );
}
