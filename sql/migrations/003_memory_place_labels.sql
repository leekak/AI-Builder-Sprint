-- 기존 Supabase 프로젝트에 한 번 실행하세요.
-- 사용자가 입력한 구체 장소와 동네 카드 그룹용 표준 태그를 분리합니다.

alter table public.memories
  add column if not exists place_label varchar(255),
  add column if not exists suggested_place_tag varchar(100);
