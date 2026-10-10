import {createSignal, For, onCleanup, onMount, Show} from 'solid-js';
import {api} from '../api/client';
import {type ChatData, type Message, mergeMessages} from '../api/types';
import {useApp} from '../app/context';
import {Close} from '../components/common';
import {dn, yo} from '../data/trips';
import {tx} from '../i18n';
import {platform} from '../platform/telegram';

export function Chat(props: { id: number }) {
  const app = useApp();
  const controller = new AbortController();
  const [info, setInfo] = createSignal<ChatData>();
  const [messages, setMessages] = createSignal<Message[]>([]);
  const [panel, setPanel] = createSignal(false);
  const [picker, setPicker] = createSignal<number>();
  const [draft, setDraft] = createSignal('');
  const [sending, setSending] = createSignal(false);
  let since = 0;
  let first = true;
  let inflight = false;
  let queued = false;
  let box!: HTMLDivElement;
  const back = () =>
    app.open({
      kind: 'chat',
      id: props.id,
    });

  async function pull() {
    if (controller.signal.aborted) {
      return;
    }
    if (inflight) {
      queued = true;
      return;
    }
    inflight = true;
    try {
      const data = await api<ChatData>(
        `/trips/${props.id}/chat?since=${since}`,
        'GET',
        undefined,
        controller.signal,
      );
      if (controller.signal.aborted) {
        return;
      }
      const stick =
        first || box.scrollTop + box.clientHeight >= box.scrollHeight - 40;
      since = Math.max(since, ...data.messages.map((m) => m.id));
      setInfo(data);
      setMessages((previous) => mergeMessages(previous, data.messages));
      if (stick) {
        queueMicrotask(() => {
          if (!controller.signal.aborted) {
            box.scrollTop = box.scrollHeight;
          }
        });
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      if (error instanceof Error && error.message === 'notmember') {
        app.close();
        app.toast(tx('err_kicked'));
        return;
      }
      if (first) {
        await app.run(async () => {
          throw error;
        });
      }
    } finally {
      first = false;
      inflight = false;
      if (queued && !controller.signal.aborted) {
        queued = false;
        void pull();
      }
    }
  }

  onMount(() => {
    void pull();
    const timer = setInterval(() => void pull(), 4000);
    onCleanup(() => {
      clearInterval(timer);
      controller.abort();
    });
  });
  const post = (path: string, body?: unknown) =>
    app.run(async () => {
      await api(path, 'POST', body, controller.signal);
      platform.haptic();
      await pull();
    });
  const react = (id: number, emoji: string) => {
    setPicker();
    void post(`/messages/${id}/react`, {
      emoji,
    });
  };

  async function send() {
    const text = draft().trim();
    if (!text || sending()) {
      return;
    }
    setSending(true);
    await app.run(async () => {
      await api(
        `/trips/${props.id}/messages`,
        'POST',
        {
          text,
        },
        controller.signal,
      );
      if (!controller.signal.aborted) {
        setDraft('');
        platform.haptic();
        await pull();
      }
    });
    setSending(false);
  }

  function system(text: string) {
    const i = text.indexOf(':');
    return tx(`sys_${text.slice(0, i)}`).replace('{n}', text.slice(i + 1));
  }

  return (
    <div class="cb">
      <Close/>
      <div class="ch">
        <b id="ct">{info() ? dn(info()?.dest || '') : ''}</b>
        <button
          type="button"
          class="ghost sm"
          id="cm"
          onClick={() => setPanel(!panel())}
        >
          {info()
            ? `👥 ${info()?.members.length} ${panel() ? '▴' : '▾'}`
            : '👥'}
        </button>
      </div>
      <div id="mp">
        <Show when={panel() && info()}>
          {(data) => (
            <div class="mpanel">
              <For each={data().members}>
                {(member) => (
                  <div class="mr">
                    <div class="mid">
                      <button
                        type="button"
                        class="lnk"
                        data-p={member.id}
                        onClick={() =>
                          app.open({
                            kind: 'profile',
                            id: member.id,
                            back,
                          })
                        }
                      >
                        {member.name}
                      </button>
                      <Show when={member.is_author}>
                        {' '}
                        <span class="tag a0">{tx('author')}</span>
                      </Show>
                      <p>
                        {member.age ? `${yo(member.age)} · ` : ''}
                        {member.a_cnt
                          ? `★ ${member.a_avg} (${member.a_cnt})`
                          : tx('newbie')}
                      </p>
                    </div>
                    <Show
                      when={
                        data().ended && member.id !== data().me && !member.rated
                      }
                    >
                      <button
                        type="button"
                        class="ghost sm"
                        data-r={member.id}
                        onClick={() =>
                          app.open({
                            kind: 'rate',
                            id: props.id,
                            only: member.id,
                          })
                        }
                      >
                        ⭐
                      </button>
                    </Show>
                    <Show
                      when={
                        data().author_id === data().me &&
                        member.id !== data().me
                      }
                    >
                      <button
                        type="button"
                        class="ghost sm"
                        data-k={member.id}
                        onClick={() =>
                          platform.confirm(
                            tx('q_kick'),
                            () =>
                              void post(`/trips/${props.id}/kick`, {
                                user_id: member.id,
                              }),
                          )
                        }
                      >
                        {tx('kick')}
                      </button>
                    </Show>
                  </div>
                )}
              </For>
              <div class="two bt">
                <Show
                  when={data().author_id === data().me}
                  fallback={
                    <button
                      type="button"
                      class="ghost"
                      id="pl"
                      onClick={() =>
                        platform.confirm(
                          tx('q_leave'),
                          () =>
                            void app.run(async () => {
                              await api(
                                `/trips/${props.id}/leave`,
                                'POST',
                                undefined,
                                controller.signal,
                              );
                              app.close();
                              app.refresh();
                            }),
                        )
                      }
                    >
                      {tx('leave')}
                    </button>
                  }
                >
                  <Show when={!data().closed && !data().ended}>
                    <button
                      type="button"
                      class="ghost"
                      id="pc"
                      onClick={() =>
                        platform.confirm(
                          tx('q_close'),
                          () =>
                            void app.run(async () => {
                              await api(
                                `/trips/${props.id}/close`,
                                'POST',
                                undefined,
                                controller.signal,
                              );
                              platform.success();
                              app.toast(tx('closedt'));
                              await pull();
                            }),
                        )
                      }
                    >
                      {tx('close')}
                    </button>
                  </Show>
                </Show>
                <button
                  type="button"
                  class="ghost"
                  id="ps"
                  onClick={() =>
                    app.share({
                      id: props.id,
                      dest: data().dest,
                    })
                  }
                >
                  🔗 {tx('share')}
                </button>
              </div>
            </div>
          )}
        </Show>
      </div>
      <p class="note">{tx('chatnote')}</p>
      <div class="msgs" id="msgs" ref={box}>
        <For each={messages()}>
          {(message) => (
            <Show
              when={message.user_id !== 0}
              fallback={<div class="m sys">{system(message.text)}</div>}
            >
              <div class={`m${message.user_id === info()?.me ? ' me' : ''}`}>
                <Show when={message.user_id !== info()?.me}>
                  <small>
                    <button
                      type="button"
                      class="lnk"
                      data-p={message.user_id}
                      onClick={() =>
                        app.open({
                          kind: 'profile',
                          id: message.user_id,
                          back,
                        })
                      }
                    >
                      {message.name}
                    </button>
                    {' '}
                    <button
                      type="button"
                      class="rp"
                      data-m={message.id}
                      aria-label={tx('report')}
                      onClick={() =>
                        app.run(async () => {
                          await api(
                            `/messages/${message.id}/report`,
                            'POST',
                            undefined,
                            controller.signal,
                          );
                          app.toast(tx('reported'));
                        })
                      }
                    >
                      ⚑
                    </button>
                  </small>
                </Show>
                {message.text}
                <button
                  type="button"
                  class="rb"
                  data-rb={message.id}
                  aria-label={tx('react')}
                  onClick={() =>
                    setPicker(picker() === message.id ? undefined : message.id)
                  }
                >
                  ☺
                </button>
                <div class="rx" data-x={message.id}>
                  <For
                    each={Object.entries(info()?.reactions[message.id] || {})}
                  >
                    {([emoji, value]) => (
                      <button
                        type="button"
                        class={`rc${value[1] ? ' on' : ''}`}
                        data-e={emoji}
                        onClick={() => react(message.id, emoji)}
                      >
                        {emoji} {value[0]}
                      </button>
                    )}
                  </For>
                </div>
                <Show when={picker() === message.id}>
                  <div class="pk">
                    <For
                      each={[
                        '👍',
                        '❤️',
                        '😂',
                        '🔥',
                        '😮',
                      ]}
                    >
                      {(emoji) => (
                        <button
                          type="button"
                          data-e={emoji}
                          onClick={() => react(message.id, emoji)}
                        >
                          {emoji}
                        </button>
                      )}
                    </For>
                  </div>
                </Show>
              </div>
            </Show>
          )}
        </For>
      </div>
      <div class="send">
        <input
          class="f"
          id="mi"
          maxlength="1000"
          placeholder={tx('msgph')}
          autocomplete="off"
          value={draft()}
          onInput={(e) => setDraft(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.isComposing) {
              void send();
            }
          }}
        />
        <button
          type="button"
          class="sb"
          id="sb"
          aria-label="Send"
          disabled={sending()}
          onClick={send}
        >
          ➤
        </button>
      </div>
    </div>
  );
}
