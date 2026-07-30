-- 기존 Supabase 프로젝트에 한 번 실행하세요.
-- 공동체 카드에 이미 반영된 비식별 조각을 개인 데이터와 분리해 보존합니다.

create table if not exists public.town_archived_fragments (
  id varchar(36) primary key,
  place_tag varchar(100) not null,
  pre_reveal_text text not null,
  post_reveal_text text not null,
  created_at timestamptz not null default now()
);

create index if not exists ix_town_archived_fragments_place_tag
  on public.town_archived_fragments(place_tag);
