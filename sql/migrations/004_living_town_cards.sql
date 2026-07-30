-- 장소별 하나의 동네 카드를 갱신하고, 동일 사용자의 여러 기여를 한 명으로 집계하기 위한 필드입니다.
alter table public.town_contributions
  add column if not exists contributor_key varchar(64);

alter table public.town_archived_fragments
  add column if not exists contributor_key varchar(64);

alter table public.town_cards
  add column if not exists published_contributor_keys jsonb not null default '[]'::jsonb,
  add column if not exists version integer not null default 1,
  add column if not exists updated_at timestamptz not null default now();

create index if not exists ix_town_contributions_contributor_key
  on public.town_contributions(contributor_key);

create index if not exists ix_town_archived_fragments_contributor_key
  on public.town_archived_fragments(contributor_key);
