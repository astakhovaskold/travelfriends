export type Flag = boolean | number;

export interface Stats {
  trips: number;
  friends: number;
  cnt: number;
  avg: number | null;
}

export interface Me extends Stats {
  id: number;
  name: string;
  age: number | null;
  city: string;
  about: string;
  vibe: string;
  rules_ok: Flag;
  registered: Flag;
  minor?: Flag;
  banned?: Flag;
}

export interface Member {
  id: number;
  name: string;
  age: number | null;
  a_cnt: number;
  a_avg: number | null;
  rated?: Flag;
  is_author?: boolean;
}

export interface Trip {
  id: number;
  user_id: number;
  author_id: number;
  dest: string;
  country: string;
  kind: string;
  date_from: string;
  date_to: string;
  people: number;
  budget: string;
  note: string;
  created: number;
  lat?: number | null;
  lon?: number | null;
  name: string;
  age: number | null;
  city: string;
  about: string;
  a_vibe: string;
  a_cnt: number;
  a_avg: number | null;
  mine: boolean;
  joined: number;
  boosted: number;
  ended: boolean;
  closed: number;
  chat_open: number;
  approval: number;
  audience: string;
  min_age: number;
  max_age: number;
  pending: number;
  req: string | null;
  members: number;
  to_rate?: number;
}

export interface MyTrips {
  mine: Trip[];
  joined: Trip[];
}

export interface People {
  dest: string;
  me: number;
  author_id: number;
  ended: boolean;
  closed: boolean;
  members: Member[];
}

export interface Message {
  id: number;
  user_id: number;
  text: string;
  name: string;
  created: number;
}

export type Reactions = Record<
  string,
  Record<
    string,
    [
      number,
      number,
    ]
  >
>;

export interface ChatData extends People {
  messages: Message[];
  reactions: Reactions;
}

export interface PublicProfile extends Stats {
  id: number;
  name: string;
  age: number | null;
  city: string;
  about: string;
  vibe: string[];
  tags: Record<string, number>;
  me: boolean;
  blocked: boolean;
  reviews: {
    stars: number;
    name: string;
    dest: string;
    tags: string[];
    text: string;
  }[];
}

export function splitVibes(
  value: string | string[] | null | undefined,
): string[] {
  return Array.isArray(value)
    ? value
    : (value || '').split(',').filter(Boolean);
}

export function mergeMessages(previous: Message[], incoming: Message[]) {
  return [
    ...new Map(
      [
        ...previous,
        ...incoming,
      ].map((message) => [
        message.id,
        message,
      ]),
    ).values(),
  ].sort((a, b) => a.id - b.id);
}
