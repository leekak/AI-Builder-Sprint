-- Nano Banana로 생성한 추억 카드 이미지의 비공개 Storage 경로와 생성 상태를 저장합니다.
alter table public.memory_cards
  add column if not exists generated_image_path varchar(500),
  add column if not exists generated_image_filename varchar(255),
  add column if not exists generated_image_content_type varchar(100),
  add column if not exists image_generation_status varchar(30) not null default 'not_requested',
  add column if not exists image_generation_mode varchar(40),
  add column if not exists image_generation_style varchar(60),
  add column if not exists image_generation_prompt text,
  add column if not exists image_generated_at timestamptz;
