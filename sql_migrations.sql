-- ══════════════════════════════════════════════════════════════════
-- Camp-Bot: добавление недостающих таблиц, индексов и начальных данных
-- Запустить в Supabase SQL Editor
-- ══════════════════════════════════════════════════════════════════

-- ── 1. Таблица звонков родителям (F79/F80) ─────────────────────────
CREATE TABLE IF NOT EXISTS call_logs (
    id          SERIAL PRIMARY KEY,
    child_id    INTEGER NOT NULL REFERENCES children(id) ON DELETE CASCADE,
    staff_id    INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    called_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note        TEXT
);

CREATE INDEX IF NOT EXISTS idx_call_logs_child   ON call_logs(child_id);
CREATE INDEX IF NOT EXISTS idx_call_logs_staff   ON call_logs(staff_id);
CREATE INDEX IF NOT EXISTS idx_call_logs_date    ON call_logs(called_at);

-- ── 2. Таблица заметок (F89–F93) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS notes (
    id          SERIAL PRIMARY KEY,
    author_id   INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    child_id    INTEGER REFERENCES children(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    pinned      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_author  ON notes(author_id);
CREATE INDEX IF NOT EXISTS idx_notes_child   ON notes(child_id);
CREATE INDEX IF NOT EXISTS idx_notes_pinned  ON notes(author_id, pinned);

-- ── 3. Уникальный индекс circle_attendance (F: DB Integrity) ───────
-- Нужен для ON CONFLICT DO UPDATE в CircleAttendance
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_circle_attendance'
    ) THEN
        ALTER TABLE circle_attendance
            ADD CONSTRAINT uq_circle_attendance
            UNIQUE (circle_id, child_id, date);
    END IF;
END $$;

-- ── 4. Индексы для задач (F: DB Integrity) ─────────────────────────
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline     ON tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_status       ON tasks(status);

-- ── 5. Индекс для напоминаний ───────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_reminders_send_at_sent
    ON reminders(send_at, sent) WHERE sent = FALSE;

-- ── 6. Составной индекс для дежурств ───────────────────────────────
CREATE INDEX IF NOT EXISTS idx_duties_date_session
    ON duties(date, session_id);

-- ── 7. Каскады: инциденты → дети ───────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'incidents_child_id_fkey'
    ) THEN
        ALTER TABLE incidents DROP CONSTRAINT incidents_child_id_fkey;
        ALTER TABLE incidents
            ADD CONSTRAINT incidents_child_id_fkey
            FOREIGN KEY (child_id) REFERENCES children(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- ── 8. Каскады: задачи → сессии ─────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'tasks_session_id_fkey'
    ) THEN
        ALTER TABLE tasks DROP CONSTRAINT tasks_session_id_fkey;
        ALTER TABLE tasks
            ADD CONSTRAINT tasks_session_id_fkey
            FOREIGN KEY (session_id) REFERENCES sessions(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- ── 9. 14 отрядов (вставляются только если не существуют) ──────────
INSERT INTO squads (name) VALUES
    ('Отряд 1'),  ('Отряд 2'),  ('Отряд 3'),  ('Отряд 4'),
    ('Отряд 5'),  ('Отряд 6'),  ('Отряд 7'),  ('Отряд 8'),
    ('Отряд 9'),  ('Отряд 10'), ('Отряд 11'), ('Отряд 12'),
    ('Отряд 13'), ('Отряд 14')
ON CONFLICT DO NOTHING;

-- Проверка результата
SELECT 'Таблицы:' AS info;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('call_logs','notes','circle_attendance','tasks','reminders','duties','squads')
ORDER BY table_name;

SELECT 'Отряды:' AS info;
SELECT id, name FROM squads ORDER BY id;
