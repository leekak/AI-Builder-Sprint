-- Supabase SQL Editor에서 실행할 수 있는 참고 스키마입니다.
-- FastAPI가 DATABASE_URL로 직접 연결하면 AUTO_CREATE_TABLES=true로도 생성 가능합니다.

create table if not exists public.memories (
  id varchar(36) primary key,
  owner_id varchar(128) not null,
  contributor_key varchar(64),
  comment text not null,
  memory_date date not null,
  place_label varchar(255),
  image_path varchar(512),
  image_filename varchar(255),
  image_content_type varchar(100),
  use_ocr boolean not null default false,
  ocr_status varchar(32) not null default 'pending',
  ocr_text text,
  ocr_error text,
  extraction_status varchar(32) not null default 'pending',
  extracted_context jsonb not null default '{}'::jsonb,
  extraction_error text,
  analysis_status varchar(32) not null default 'pending',
  analysis jsonb not null default '{}'::jsonb,
  analysis_error text,
  first_recall_at timestamptz not null,
  second_recall_at timestamptz not null,
  current_recall_stage integer not null default 1,
  recall_completed boolean not null default false,
  place_tag varchar(100),
  suggested_place_tag varchar(100),
  share_to_town boolean not null default false,
  status varchar(32) not null default 'registered',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ix_memories_owner_id on public.memories(owner_id);
create index if not exists ix_memories_owner_due_stage on public.memories(owner_id, current_recall_stage, recall_completed);

create table if not exists public.recall_sessions (
  id varchar(36) primary key,
  memory_id varchar(36) not null references public.memories(id) on delete cascade,
  owner_id varchar(128) not null,
  stage integer not null,
  status varchar(32) not null default 'created',
  questions jsonb not null default '[]'::jsonb,
  initial_answer text,
  hint_answers jsonb not null default '[]'::jsonb,
  hint_level integer not null default 0,
  memory_not_recalled boolean not null default false,
  newly_recalled_text text,
  started_at timestamptz not null default now(),
  answered_at timestamptz,
  revealed_at timestamptz,
  completed_at timestamptz,
  constraint uq_recall_memory_stage unique(memory_id, stage)
);

create index if not exists ix_recall_sessions_owner_id on public.recall_sessions(owner_id);

create table if not exists public.memory_cards (
  id varchar(36) primary key,
  memory_id varchar(36) not null references public.memories(id) on delete cascade,
  recall_id varchar(36) not null unique references public.recall_sessions(id) on delete cascade,
  owner_id varchar(128) not null,
  card_title varchar(255) not null,
  story text not null,
  reflection text not null,
  newly_recalled_details jsonb not null default '[]'::jsonb,
  archived boolean not null default false,
  shared_to_town boolean not null default false,
  place_tag varchar(100),
  generated_image_path varchar(500),
  generated_image_filename varchar(255),
  generated_image_content_type varchar(100),
  image_generation_status varchar(30) not null default 'not_requested',
  image_generation_mode varchar(40),
  image_generation_style varchar(60),
  image_generation_prompt text,
  image_generated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ix_memory_cards_owner_id on public.memory_cards(owner_id);

create table if not exists public.town_contributions (
  id varchar(36) primary key,
  card_id varchar(36) not null unique references public.memory_cards(id) on delete cascade,
  memory_id varchar(36) not null references public.memories(id) on delete cascade,
  recall_id varchar(36) not null references public.recall_sessions(id) on delete cascade,
  owner_id varchar(128) not null,
  place_tag varchar(100) not null,
  pre_reveal_text text not null,
  post_reveal_text text not null,
  created_at timestamptz not null default now()
);

create index if not exists ix_town_contributions_place_tag on public.town_contributions(place_tag);
create index if not exists ix_town_contributions_owner_id on public.town_contributions(owner_id);
create index if not exists ix_town_contributions_contributor_key on public.town_contributions(contributor_key);

-- 이미 공동체 카드에 반영된 조각은 개인 기억 삭제 시 사용자 연결을 제거한 뒤 이곳에 보존합니다.
create table if not exists public.town_archived_fragments (
  id varchar(36) primary key,
  place_tag varchar(100) not null,
  contributor_key varchar(64),
  pre_reveal_text text not null,
  post_reveal_text text not null,
  created_at timestamptz not null default now()
);

create index if not exists ix_town_archived_fragments_place_tag on public.town_archived_fragments(place_tag);
create index if not exists ix_town_archived_fragments_contributor_key on public.town_archived_fragments(contributor_key);

create table if not exists public.town_cards (
  id varchar(36) primary key,
  place_tag varchar(100) not null,
  contributors integer not null,
  card_title varchar(255) not null,
  story text not null,
  reflection text not null,
  source_contribution_ids jsonb not null default '[]'::jsonb,
  published_contributor_keys jsonb not null default '[]'::jsonb,
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ix_town_cards_place_tag on public.town_cards(place_tag);

-- Storage bucket: 원본 이미지는 public이 아닌 private bucket에 저장합니다.
insert into storage.buckets (id, name, public)
values ('memory-images', 'memory-images', false)
on conflict (id) do nothing;

-- 이 프로젝트의 FastAPI 서버는 service role key를 사용해 Storage에 접근하고,
-- /memories/{id}/image 엔드포인트에서 소유자를 확인한 뒤 이미지를 프록시합니다.
-- 서비스 역할 키는 절대 프런트엔드에 노출하지 마세요.
