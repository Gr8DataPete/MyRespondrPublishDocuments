-- Run this in your Supabase SQL editor for the upload project to create the Organization_Documents table

create table if not exists public."Organization_Documents" (
  document_id uuid primary key,
  user_id uuid,
  org_id uuid,
  filename text,
  storage_path text,
  bucket text,
  content_type text,
  size_bytes bigint,
  description text,
  created_at timestamptz default now()
);

-- Optional index for fast lookup by organization
create index if not exists idx_organization_documents_org_id on public."Organization_Documents" (org_id);

-- Optional index for lookup by user
create index if not exists idx_organization_documents_user_id on public."Organization_Documents" (user_id);
