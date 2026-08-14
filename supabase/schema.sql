-- QWEEN AI Tools — Supabase schema for the system settings / prompts store.
-- Run this once in the Supabase SQL editor (Dashboard -> SQL Editor -> New query).
--
-- The backend talks to these tables with the service_role key, which bypasses
-- row-level security, so the tables are only ever reachable from the backend.
-- They are NOT exposed to the browser.

create table if not exists app_settings (
    tool_id    text primary key,
    settings   jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists app_prompts (
    id         uuid primary key default gen_random_uuid(),
    tool_id    text not null,
    name       text not null,
    prompt     text not null default '',
    updated_at timestamptz not null default now(),
    unique (tool_id, name)
);

-- Keep RLS enabled with no public policies. The service_role key used by the
-- backend bypasses RLS; the anon/publishable key gets no access at all.
alter table app_settings enable row level security;
alter table app_prompts  enable row level security;

-- Optional seed: the upscaler's editable defaults. Adjust as you like, or set
-- them later via  PUT /api/settings.
insert into app_settings (tool_id, settings)
values (
    'upscaler',
    '{"default_scale_factor": 2, "default_concurrency": 4, "default_suffix": "", "default_output_format": "jpeg", "usd_to_inr": 90}'::jsonb
)
on conflict (tool_id) do nothing;
