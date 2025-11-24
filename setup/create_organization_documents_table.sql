-- Run this in your Supabase SQL editor to create the table that stores document metadata

create table if not exists public."OrganizationDocuments" (
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

-- Add an index for org_id for faster listing by organization
create index if not exists idx_organizationdocuments_org_id on public."OrganizationDocuments" (org_id);
