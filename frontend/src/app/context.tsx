import {type Accessor, createContext, useContext} from 'solid-js';
import type {Me, Trip} from '../api/types';

export type Tab = 'board' | 'places' | 'chat' | 'pass';
export type Modal =
  | {
  kind: 'trip';
  trip: Trip;
}
  | {
  kind: 'requests';
  trip: Trip;
}
  | {
  kind: 'chat';
  id: number;
}
  | {
  kind: 'profile';
  id: number;
  back?: () => void;
}
  | {
  kind: 'rate';
  id: number;
  only?: number;
}
  | {
  kind: 'onboarding';
  must: boolean;
}
  | {
  kind: 'rules' | 'minor' | 'register' | 'create' | 'language';
}
  | {
  kind: 'edit';
  me: Me;
};

export interface AppState {
  tab: Accessor<Tab>;
  revision: Accessor<number>;
  me: Accessor<Me | undefined>;
  modal: Accessor<Modal | null>;
  query: Accessor<string>;
  kind: Accessor<string>;
  place: Accessor<string>;
  list: Accessor<Trip[]>;

  show(tab: Tab): void;

  refresh(): void;

  refreshMe(): Promise<Me>;

  open(modal: Modal): void;

  close(): void;

  run(action: () => Promise<unknown>): Promise<void>;

  toast(text: string): void;

  share(trip: Pick<Trip, 'id' | 'dest'> & Partial<Pick<Trip, 'kind'>>): void;

  setQuery(value: string): void;

  setKind(value: string): void;

  setPlace(value: string): void;

  setList(value: Trip[]): void;
}

export const AppContext = createContext<AppState>();

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('Missing app context');
  }
  return context;
}
