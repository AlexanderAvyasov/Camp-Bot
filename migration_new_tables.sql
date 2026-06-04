-- Migration: new tables for duties, incidents, checklists, announcements, ratings, circles, reminders
-- Run in Supabase SQL editor

-- Reminders
CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    send_at TIMESTAMPTZ NOT NULL,
    sent BOOLEAN NOT NULL DEFAULT FALSE,
    text TEXT NOT NULL
);

-- Duties
CREATE TYPE IF NOT EXISTS duty_type AS ENUM ('dining', 'territory', 'dormitory', 'night');
CREATE TYPE IF NOT EXISTS duty_status AS ENUM ('scheduled', 'active', 'completed');

CREATE TABLE IF NOT EXISTS duties (
    id SERIAL PRIMARY KEY,
    type duty_type NOT NULL,
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    date DATE NOT NULL,
    status duty_status NOT NULL DEFAULT 'scheduled',
    session_id INTEGER REFERENCES sessions(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS duty_checkpoints (
    id SERIAL PRIMARY KEY,
    duty_id INTEGER NOT NULL REFERENCES duties(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    confirmed_at TIMESTAMPTZ
);

-- Incidents
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    type VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    reported_by INTEGER NOT NULL REFERENCES staff(id),
    child_id INTEGER REFERENCES children(id),
    photo_url TEXT,
    session_id INTEGER REFERENCES sessions(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Checklists
CREATE TYPE IF NOT EXISTS checklist_type AS ENUM ('pre_event', 'lights_out');

CREATE TABLE IF NOT EXISTS checklist_templates (
    id SERIAL PRIMARY KEY,
    type checklist_type NOT NULL,
    title VARCHAR(256) NOT NULL,
    session_id INTEGER REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS checklist_items (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES checklist_templates(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS checklist_runs (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES checklist_templates(id),
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    event_id INTEGER REFERENCES events(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS checklist_item_results (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES checklist_runs(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES checklist_items(id),
    confirmed_at TIMESTAMPTZ
);

-- Announcements
CREATE TABLE IF NOT EXISTS announcements (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES staff(id),
    session_id INTEGER REFERENCES sessions(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS announcement_reads (
    announcement_id INTEGER NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (announcement_id, staff_id)
);

-- Event ratings
CREATE TABLE IF NOT EXISTS event_ratings (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Circles
CREATE TABLE IF NOT EXISTS circles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    leader_id INTEGER REFERENCES staff(id),
    session_id INTEGER REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS circle_schedules (
    id SERIAL PRIMARY KEY,
    circle_id INTEGER NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    time TIME NOT NULL
);

CREATE TABLE IF NOT EXISTS circle_members (
    circle_id INTEGER NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    child_id INTEGER NOT NULL REFERENCES children(id) ON DELETE CASCADE,
    PRIMARY KEY (circle_id, child_id)
);

CREATE TABLE IF NOT EXISTS circle_attendance (
    id SERIAL PRIMARY KEY,
    circle_id INTEGER NOT NULL REFERENCES circles(id),
    child_id INTEGER NOT NULL REFERENCES children(id),
    date DATE NOT NULL,
    present BOOLEAN NOT NULL DEFAULT TRUE
);

-- Add circle_leader role if not exists (PostgreSQL enum alter)
-- Note: PostgreSQL does not support IF NOT EXISTS for enum values; run only if not already added
ALTER TYPE staffrole ADD VALUE IF NOT EXISTS 'circle_leader';
