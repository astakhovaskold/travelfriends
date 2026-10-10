import {
  createEffect,
  createMemo,
  createSignal,
  For,
  onCleanup,
  onMount,
  untrack,
} from 'solid-js';
import type {Trip} from '../api/types';
import {ci, dn, ke, pinCoord} from '../data/trips';
import {WLD} from '../data/world';
import {platform} from '../platform/telegram';

const MW = 1000;
const MH = 394;
const xy = (
  c: [
    number,
    number,
  ],
) => [
  ((c[1] + 180) / 360) * MW,
  ((84 - c[0]) / 142) * MH,
];

export function WorldMap(props: {
  trips?: Trip[];
  selected?: string;
  onSelect?: (dest: string) => void;
  coordinate?: [
    number,
    number,
  ];
  country?: boolean;
}) {
  let root!: HTMLDivElement;
  const [size, setSize] = createSignal([
    340,
    200,
  ]);
  const [labelZoom, setLabelZoom] = createSignal(1);
  const [view, setView] = createSignal({
    k: 1,
    x: 0,
    y: 0,
  });
  const base = () => Math.max(size()[0] / MW, size()[1] / MH);
  const scale = () => base() * view().k;
  const groups = createMemo(() => {
    const map = new Map<
      string,
      {
        c: [
          number,
          number,
        ];
        items: Trip[];
      }
    >();
    for (const trip of props.trips || []) {
      const c = pinCoord(trip);
      if (!c) {
        continue;
      }
      const group = map.get(trip.dest) || {
        c,
        items: [],
      };
      group.items.push(trip);
      map.set(trip.dest, group);
    }
    return [
      ...map.entries(),
    ];
  });
  const apply = (k: number, x: number, y: number) => {
    const clampedZoom = Math.min(Math.max(k, 1), props.coordinate ? 40 : 30);
    const s = base() * clampedZoom;
    setView({
      k: clampedZoom,
      x: Math.min(0, Math.max(size()[0] - MW * s, x)),
      y: Math.min(0, Math.max(size()[1] - MH * s, y)),
    });
  };

  function focus(
    c: [
      number,
      number,
    ],
    k: number,
  ) {
    const q = xy(c);
    const s = base() * k;
    apply(k, size()[0] / 2 - q[0] * s, size()[1] / 2 - q[1] * s);
  }

  function fit() {
    const points = groups().map(([, g]) => xy(g.c));
    if (!points.length) {
      apply(1, 0, 0);
      return;
    }
    const x1 = Math.min(...points.map((p) => p[0]));
    const x2 = Math.max(...points.map((p) => p[0]));
    const y1 = Math.min(...points.map((p) => p[1]));
    const y2 = Math.max(...points.map((p) => p[1]));
    const k = Math.min(
      Math.max(
        Math.min(
          (size()[0] * 0.7) / (Math.max(x2 - x1, 40) * base()),
          (size()[1] * 0.7) / (Math.max(y2 - y1, 40) * base()),
        ),
        1,
      ),
      5,
    );
    const s = base() * k;
    apply(
      k,
      size()[0] / 2 - ((x1 + x2) / 2) * s,
      size()[1] / 2 - ((y1 + y2) / 2) * s,
    );
  }

  function zoom(f: number, px: number, py: number) {
    const v = view();
    const wx = (px - v.x) / scale();
    const wy = (py - v.y) / scale();
    const k = Math.min(Math.max(v.k * f, 1), 30);
    const s = base() * k;
    apply(k, px - wx * s, py - wy * s);
  }

  const pointers = new Map<
    number,
    [
      number,
      number,
    ]
  >();
  let distance = 0;

  function down(event: PointerEvent) {
    if (props.coordinate || (event.target as Element).closest('.zb,.pw')) {
      return;
    }
    root.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, [
      event.clientX,
      event.clientY,
    ]);
  }

  function move(event: PointerEvent) {
    const previous = pointers.get(event.pointerId);
    if (!previous) {
      return;
    }
    pointers.set(event.pointerId, [
      event.clientX,
      event.clientY,
    ]);
    if (pointers.size === 1) {
      const v = view();
      apply(
        v.k,
        v.x + event.clientX - previous[0],
        v.y + event.clientY - previous[1],
      );
    } else if (pointers.size === 2) {
      const p = [
        ...pointers.values(),
      ];
      const d = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]);
      const r = root.getBoundingClientRect();
      if (distance) {
        zoom(
          d / distance,
          (p[0][0] + p[1][0]) / 2 - r.left,
          (p[0][1] + p[1][1]) / 2 - r.top,
        );
      }
      distance = d;
    }
  }

  function up(event: PointerEvent) {
    pointers.delete(event.pointerId);
    distance = 0;
  }

  onMount(() => {
    setSize([
      root.clientWidth || 340,
      root.clientHeight || 200,
    ]);
    if (props.coordinate) {
      focus(props.coordinate, props.country ? 4 : 9);
    } else {
      fit();
    }
    const observer = new ResizeObserver(() => {
      setSize([
        root.clientWidth || 340,
        root.clientHeight || 200,
      ]);
      const v = view();
      apply(v.k, v.x, v.y);
    });
    observer.observe(root);
    onCleanup(() => {
      observer.disconnect();
      pointers.clear();
    });
  });
  createEffect(() => {
    groups();
    setLabelZoom(untrack(() => view().k));
    untrack(() => {
      if (root && !props.coordinate) {
        fit();
      }
    });
  });
  const position = (
    c: [
      number,
      number,
    ],
  ) => {
    const q = xy(c);
    return {
      left: `${q[0] * scale() + view().x}px`,
      top: `${q[1] * scale() + view().y}px`,
    };
  };
  return (
    <div
      class="smap"
      ref={root}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
      onDblClick={(e) => e.preventDefault()}
    >
      <svg
        viewBox="0 0 1000 394"
        width="1000"
        height="394"
        style={{
          transform: `translate(${view().x}px,${view().y}px) scale(${scale()})`,
        }}
      >
        <rect width="1000" height="394" fill="#CFE6F7"/>
        <path
          d={WLD}
          fill="#FFFFFF"
          stroke="#D9CDB6"
          stroke-width=".6"
          stroke-linejoin="round"
        />
      </svg>
      <div class="pl">
        {props.coordinate ? (
          <div class="dot" style={position(props.coordinate)}/>
        ) : (
          <For each={groups()}>
            {([dest, group]) => (
              <button
                type="button"
                class="pw"
                style={position(group.c)}
                onClick={(event) => {
                  event.stopPropagation();
                  platform.haptic();
                  setLabelZoom(view().k);
                  const next = props.selected === dest ? '' : dest;
                  props.onSelect?.(next);
                  if (next) {
                    focus(group.c, Math.max(view().k, 4));
                  }
                }}
              >
                <div
                  class={
                    'pin a' +
                    ci(dest) +
                    (group.items.some(
                      (x) => Date.now() / 1000 - x.created < 172800,
                    )
                      ? ' fresh'
                      : '') +
                    (props.selected === dest ? ' sel' : '')
                  }
                >
                  <span>{ke(group.items[0])}</span>
                  <b>{group.items.length}</b>
                  {(labelZoom() >= 3 || props.selected === dest) && (
                    <i>{dn(dest)}</i>
                  )}
                </div>
              </button>
            )}
          </For>
        )}
      </div>
      {!props.coordinate && (
        <div class="zb">
          <button
            type="button"
            data-z="1"
            aria-label="+"
            onClick={() => zoom(1.8, size()[0] / 2, size()[1] / 2)}
          >
            +
          </button>
          <button
            type="button"
            data-z="-1"
            aria-label="−"
            onClick={() => zoom(1 / 1.8, size()[0] / 2, size()[1] / 2)}
          >
            −
          </button>
        </div>
      )}
    </div>
  );
}
