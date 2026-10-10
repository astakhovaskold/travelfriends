import {Match, Switch} from 'solid-js';

export function Icon(props: { name: string }) {
  return (
    <svg viewBox="0 0 24 24">
      <Switch>
        <Match when={props.name === 'board'}>
          <path d="M3 11.5 12 4l9 7.5"/>
          <path d="M5.5 10v9a1 1 0 0 0 1 1H10v-5h4v5h3.5a1 1 0 0 0 1-1v-9"/>
        </Match>
        <Match when={props.name === 'places'}>
          <circle cx="12" cy="12" r="9"/>
          <path d="m15.6 8.4-2.1 5.1-5.1 2.1 2.1-5.1z"/>
        </Match>
        <Match when={props.name === 'chat'}>
          <path d="M20.5 11.5a8 8 0 0 1-11.7 7.1L4 20l1.3-4.4A8 8 0 1 1 20.5 11.5z"/>
          <path d="M9 11.5h6M9 14.5h3.5"/>
        </Match>
        <Match when={props.name === 'pass'}>
          <rect x="5" y="3" width="14" height="18" rx="2.5"/>
          <circle cx="12" cy="10" r="2.6"/>
          <path d="M8.5 16.5c.8-1.6 2-2.2 3.5-2.2s2.7.6 3.5 2.2"/>
        </Match>
      </Switch>
    </svg>
  );
}
