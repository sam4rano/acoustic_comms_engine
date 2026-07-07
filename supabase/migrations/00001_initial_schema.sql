-- Enable pgvector for embedding search
create extension if not exists vector with schema public;

-- Users
create table users (
    id          uuid primary key default gen_random_uuid(),
    email       varchar(320) not null unique,
    display_name varchar(255),
    settings    jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

create index idx_users_email on users (email);

-- Sessions
create table sessions (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references users(id) on delete cascade,
    status      varchar(20) not null default 'created',
    language    varchar(10) not null default 'en',
    config      jsonb not null default '{}'::jsonb,
    started_at  timestamptz,
    ended_at    timestamptz,
    created_at  timestamptz not null default now()
);

create index idx_sessions_user_id on sessions (user_id);

-- Speakers
create table speakers (
    id           uuid primary key default gen_random_uuid(),
    session_id   uuid not null references sessions(id) on delete cascade,
    label        varchar(50) not null,
    embedding_id uuid
);

create index idx_speakers_session_id on speakers (session_id);

-- Turns
create table turns (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid not null references sessions(id) on delete cascade,
    speaker_id  uuid not null references speakers(id) on delete cascade,
    text        text not null,
    start_ms    integer not null,
    end_ms      integer not null,
    confidence  float not null check (confidence >= 0 and confidence <= 1),
    turn_index  integer not null
);

create index idx_turns_session_id on turns (session_id);
create index idx_turns_speaker_id on turns (speaker_id);

-- Embeddings (pgvector)
create table embeddings (
    id              uuid primary key default gen_random_uuid(),
    session_id      uuid not null references sessions(id) on delete cascade,
    turn_id         uuid not null references turns(id) on delete cascade,
    encoder_version varchar(64) not null,
    vector_id       uuid not null,
    dims            integer not null
);

create index idx_embeddings_session_id on embeddings (session_id);
create index idx_embeddings_turn_id on embeddings (turn_id);

-- Acoustic labels
create table acoustic_labels (
    id          uuid primary key default gen_random_uuid(),
    turn_id     uuid not null references turns(id) on delete cascade,
    head        varchar(32) not null,
    label       varchar(64) not null,
    confidence  float not null check (confidence >= 0 and confidence <= 1),
    extra_meta  jsonb
);

create index idx_acoustic_labels_turn_id on acoustic_labels (turn_id);

-- Audio events
create table audio_events (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid not null references sessions(id) on delete cascade,
    turn_id     uuid references turns(id) on delete set null,
    event_type  varchar(32) not null,
    start_ms    integer not null,
    end_ms      integer not null,
    confidence  float not null default 1.0 check (confidence >= 0 and confidence <= 1)
);

create index idx_audio_events_session_id on audio_events (session_id);

-- Analysis reports
create table analysis_reports (
    id                  uuid primary key default gen_random_uuid(),
    session_id          uuid not null references sessions(id) on delete cascade,
    status              varchar(20) not null default 'in_progress',
    scores              jsonb,
    coaching            jsonb,
    agent_trace         jsonb,
    degraded            boolean not null default false,
    degradation_reason  text,
    created_at          timestamptz not null default now(),
    completed_at        timestamptz
);

create index idx_analysis_reports_session_id on analysis_reports (session_id);

-- Memory documents
create table memory_documents (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid not null references users(id) on delete cascade,
    title        varchar(255) not null,
    content      text not null,
    embedding_id uuid,
    created_at   timestamptz not null default now()
);

create index idx_memory_documents_user_id on memory_documents (user_id);

-- RLS — enable on all tables (defense in depth)
alter table users enable row level security;
alter table sessions enable row level security;
alter table speakers enable row level security;
alter table turns enable row level security;
alter table embeddings enable row level security;
alter table acoustic_labels enable row level security;
alter table audio_events enable row level security;
alter table analysis_reports enable row level security;
alter table memory_documents enable row level security;

-- Per-service-role policies for backend access
-- The backend connects via DATABASE_URL with full access.
-- These policies keep the Data API safe when exposed.
create policy "Service role full access" on users for all to service_role using (true);
create policy "Service role full access" on sessions for all to service_role using (true);
create policy "Service role full access" on speakers for all to service_role using (true);
create policy "Service role full access" on turns for all to service_role using (true);
create policy "Service role full access" on embeddings for all to service_role using (true);
create policy "Service role full access" on acoustic_labels for all to service_role using (true);
create policy "Service role full access" on audio_events for all to service_role using (true);
create policy "Service role full access" on analysis_reports for all to service_role using (true);
create policy "Service role full access" on memory_documents for all to service_role using (true);
