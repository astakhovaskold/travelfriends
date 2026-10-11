import {createSignal, For, Match, onCleanup, onMount, Show, Switch,} from 'solid-js';
import {api} from '../api/client';
import type {Me, Trip} from '../api/types';
import {Close} from '../components/common';
import {Icon} from '../components/Icon';
import {SplashLogo} from '../components/SplashLogo';
import {dn, ke} from '../data/trips';
import {Board} from '../features/Board';
import {Chat} from '../features/Chat';
import {ChatList} from '../features/ChatList';
import {Minor, Onboarding, Rules} from '../features/Onboarding';
import {Places} from '../features/Places';
import {Passport, Profile, ProfileForm} from '../features/Profile';
import {Requests} from '../features/Requests';
import {Review} from '../features/Review';
import {TripDetails} from '../features/TripDetails';
import {TripForm} from '../features/TripForm';
import {LANGS, language, setLanguage, tx} from '../i18n';
import {platform} from '../platform/telegram';
import {AppContext, type Modal, type Tab} from './context';

export function App() {
  const [tab, setTab] = createSignal<Tab>('board');
  const [revision, setRevision] = createSignal(0);
  const [modal, setModal] = createSignal<Modal | null>(null);
  const [me, setMe] = createSignal<Me>();
  const [list, setList] = createSignal<Trip[]>([]);
  const [query, setQuery] = createSignal('');
  const [kind, setKind] = createSignal('all');
  const [place, setPlace] = createSignal('');
  const [splash, setSplash] = createSignal(true);
  const [toasts, setToasts] = createSignal<
    {
      id: number;
      text: string;
    }[]
  >([]);
  const controller = new AbortController();
  const timers = new Set<ReturnType<typeof setTimeout>>();
  let bot = '';
  let toastId = 0;
  const later = (fn: () => void, ms: number) => {
    const timer = setTimeout(() => {
      timers.delete(timer);
      fn();
    }, ms);
    timers.add(timer);
  };

  function toast(text: string) {
    const id = ++toastId;
    setToasts([
      ...toasts(),
      {
        id,
        text,
      },
    ]);
    later(() => setToasts((items) => items.filter((t) => t.id !== id)), 2600);
  }

  const locked = () =>
    modal()?.kind === 'register' ||
    modal()?.kind === 'minor' ||
    (modal()?.kind === 'onboarding' &&
      (
        modal() as {
          must: boolean;
        }
      ).must);
  const close = () => setModal(null);
  const open = (value: Modal) => {
    platform.haptic(value.kind === 'trip' ? 'medium' : 'light');
    setModal(value);
  };
  const refresh = () => setRevision(revision() + 1);
  const show = (value: Tab) => {
    setTab(value);
    refresh();
  };

  async function refreshMe() {
    const value = await api<Me>('/me', 'GET', undefined, controller.signal);
    if (!controller.signal.aborted) {
      setMe(value);
    }
    return value;
  }

  async function gate() {
    if (locked()) {
      return;
    }
    const value = await refreshMe();
    openGate(value);
  }

  function openGate(value: Me) {
    if (!value.registered) {
      open({
        kind: 'register',
      });
    }
  }

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      const message = error instanceof Error ? error.message : 'Error';
      if (message === 'rules' || message === 'register') {
        try {
          await gate();
        } catch (e) {
          toast(
            e instanceof Error ? tx(`err_${e.message}`) || e.message : 'Error',
          );
        }
        return;
      }
      if (message === 'minor') {
        open({
          kind: 'minor',
        });
        return;
      }
      toast(tx(`err_${message}`) || message);
    }
  }

  async function deep() {
    const params = new URLSearchParams(location.search);
    const request = params.get('req');
    const chat = params.get('chat');
    const rate = params.get('rate');
    const trip = params.get('trip');
    if (request) {
      open({
        kind: 'requests',
        trip: await api<Trip>(
          `/trips/${+request}`,
          'GET',
          undefined,
          controller.signal,
        ),
      });
    } else if (chat) {
      open({
        kind: 'chat',
        id: +chat,
      });
    } else if (rate) {
      open({
        kind: 'rate',
        id: +rate,
      });
    } else if (trip) {
      open({
        kind: 'trip',
        trip: await api<Trip>(
          `/trips/${+trip}`,
          'GET',
          undefined,
          controller.signal,
        ),
      });
    }
  }

  function share(
    trip: Pick<Trip, 'id' | 'dest'> & Partial<Pick<Trip, 'kind'>>,
  ) {
    if (!bot) {
      toast(tx('err_notfound'));
      return;
    }
    const link = `https://t.me/${bot}?start=trip_${trip.id}`;
    platform.share(
      'https://t.me/share/url?url=' +
      encodeURIComponent(link) +
      '&text=' +
      encodeURIComponent(
        `${ke({
          kind: trip.kind || 'flight',
        })} ${dn(trip.dest)}: ${tx('sharetxt')}`,
      ),
    );
  }

  onMount(() => {
    platform.initialize();
    document.documentElement.lang = language();
    void api<{
      bot: string;
    }>('/config', 'GET', undefined, controller.signal)
      .then((config) => (bot = config.bot || ''))
      .catch(() => {
      });
    later(() => setSplash(false), 3600);
    later(
      () =>
        void run(async () => {
          const value = await refreshMe();
          if (value.rules_ok && value.registered) {
            await deep();
          } else {
            openGate(value);
          }
        }),
      2800,
    );
    const prevent = (event: Event) => event.preventDefault();
    document.addEventListener('gesturestart', prevent);
    document.addEventListener('dblclick', prevent);
    onCleanup(() => {
      controller.abort();
      timers.forEach(clearTimeout);
      document.removeEventListener('gesturestart', prevent);
      document.removeEventListener('dblclick', prevent);
    });
  });
  return (
    <AppContext.Provider
      value={{
        tab,
        show,
        revision,
        refresh,
        me,
        refreshMe,
        modal,
        open,
        close,
        run,
        toast,
        share,
        query,
        setQuery,
        kind,
        setKind,
        place,
        setPlace,
        list,
        setList,
      }}
    >
      <div
        id="splash"
        class={splash() ? '' : 'out'}
        onClick={() => setSplash(false)}
      >
        <SplashLogo/>
        <h1>Travel Friends</h1>
        <p id="tag">{tx('tag')}</p>
        <p id="tag2">{tx('tag2')}</p>
        <div class="sl">
          <For each={LANGS}>
            {(l) => (
              <button
                type="button"
                data-l={l[0]}
                class={l[0] === language() ? 'on' : ''}
                onClick={(e) => {
                  e.stopPropagation();
                  setLanguage(l[0]);
                  platform.haptic();
                  refresh();
                }}
              >
                {l[2]} {l[0].toUpperCase()}
              </button>
            )}
          </For>
        </div>
      </div>
      <div id="app">
        <div class="top">
          <span class="logo">Travel Friends</span>
          <span>
            <button
              type="button"
              class="lang"
              id="help"
              aria-label={tx('howto')}
              onClick={() =>
                open({
                  kind: 'onboarding',
                  must: false,
                })
              }
            >
              ?
            </button>
            {' '}
            <button
              type="button"
              class="lang"
              id="lang"
              onClick={() =>
                open({
                  kind: 'language',
                })
              }
            >
              {LANGS.find((l) => l[0] === language())?.[2]}{' '}
              <b>{language().toUpperCase()}</b>
            </button>
          </span>
        </div>
        <div id="body">
          <Switch>
            <Match when={tab() === 'board'}>
              <Board/>
            </Match>
            <Match when={tab() === 'places'}>
              <Places/>
            </Match>
            <Match when={tab() === 'chat'}>
              <ChatList/>
            </Match>
            <Match when={tab() === 'pass'}>
              <Passport/>
            </Match>
          </Switch>
        </div>
        <nav>
          <For
            each={
              [
                'board',
                'places',
              ] as Tab[]
            }
          >
            {(value) => (
              <button
                type="button"
                id={`n_${value}`}
                aria-current={tab() === value}
                onClick={() => show(value)}
              >
                <Icon name={value}/>
                <span>{tx(value)}</span>
              </button>
            )}
          </For>
          <button
            type="button"
            class="navplus"
            id="plus"
            aria-label={tx('create')}
            onClick={() =>
              open({
                kind: 'create',
              })
            }
          >
            +
          </button>
          <For
            each={
              [
                'chat',
                'pass',
              ] as Tab[]
            }
          >
            {(value) => (
              <button
                type="button"
                id={`n_${value}`}
                aria-current={tab() === value}
                onClick={() => show(value)}
              >
                <Icon name={value}/>
                <span>{tx(value === 'pass' ? 'passport' : value)}</span>
              </button>
            )}
          </For>
        </nav>
      </div>
      <div
        class={`ms${modal() ? ' on' : ''}`}
        id="ms"
        onClick={(e) => {
          if (e.target === e.currentTarget && !locked()) {
            close();
          }
        }}
      >
        <div class="mb" id="mb">
          <Show when={modal()} keyed>
            {(value) => (
              <Switch>
                <Match when={value.kind === 'trip'}>
                  <TripDetails
                    trip={
                      (
                        value as Extract<
                          Modal,
                          {
                            kind: 'trip';
                          }
                        >
                      ).trip
                    }
                  />
                </Match>
                <Match when={value.kind === 'requests'}>
                  <Requests
                    trip={
                      (
                        value as Extract<
                          Modal,
                          {
                            kind: 'requests';
                          }
                        >
                      ).trip
                    }
                  />
                </Match>
                <Match when={value.kind === 'chat'}>
                  <Chat
                    id={
                      (
                        value as Extract<
                          Modal,
                          {
                            kind: 'chat';
                          }
                        >
                      ).id
                    }
                  />
                </Match>
                <Match when={value.kind === 'profile'}>
                  <Profile
                    {...(value as Extract<
                      Modal,
                      {
                        kind: 'profile';
                      }
                    >)}
                  />
                </Match>
                <Match when={value.kind === 'rate'}>
                  <Review
                    {...(value as Extract<
                      Modal,
                      {
                        kind: 'rate';
                      }
                    >)}
                  />
                </Match>
                <Match when={value.kind === 'onboarding'}>
                  <Onboarding
                    must={
                      (
                        value as Extract<
                          Modal,
                          {
                            kind: 'onboarding';
                          }
                        >
                      ).must
                    }
                  />
                </Match>
                <Match when={value.kind === 'rules'}>
                  <Rules/>
                </Match>
                <Match when={value.kind === 'minor'}>
                  <Minor/>
                </Match>
                <Match when={value.kind === 'register'}>
                  <ProfileForm/>
                </Match>
                <Match when={value.kind === 'edit'}>
                  <ProfileForm
                    me={
                      (
                        value as Extract<
                          Modal,
                          {
                            kind: 'edit';
                          }
                        >
                      ).me
                    }
                  />
                </Match>
                <Match when={value.kind === 'create'}>
                  <TripForm/>
                </Match>
                <Match when={value.kind === 'language'}>
                  <div class="form">
                    <Close/>
                    <h2>🌐 {tx('langt')}</h2>
                    <For each={LANGS}>
                      {(l) => (
                        <button
                          type="button"
                          class="cta alt text-left"
                          data-l={l[0]}
                          style={{
                            'border-color':
                              l[0] === language() ? 'var(--a0)' : undefined,
                          }}
                          onClick={() => {
                            close();
                            setLanguage(l[0]);
                            platform.haptic();
                            refresh();
                          }}
                        >
                          {l[2]} {l[1]}
                        </button>
                      )}
                    </For>
                  </div>
                </Match>
              </Switch>
            )}
          </Show>
        </div>
      </div>
      <For each={toasts()}>
        {(item) => <div class="toast">{item.text}</div>}
      </For>
    </AppContext.Provider>
  );
}
