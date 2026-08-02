-- 관리자 삭제 카드를 복구할 수 있도록 영구 삭제 대신 소프트 삭제 상태를 저장합니다.
alter table public.town_cards
  add column if not exists deleted_at timestamptz,
  add column if not exists deleted_by varchar(100);

create index if not exists ix_town_cards_deleted_at
  on public.town_cards(deleted_at);
