-- seed.sql: baseline triggers and default admin user
-- Run after schema.sql to populate initial data.
-- All passwords must be changed before production use.

-- ------------------------------------------------------------------ --
-- Baseline trigger rules (mirrors classify_rules.py BASELINE_TRIGGERS) --
-- ------------------------------------------------------------------ --

INSERT INTO triggers (code, description, regex_patterns, keywords, negative_keywords, weight, enabled)
VALUES
  (
    'need_help',
    'Ищут помощь или исполнителя',
    '["кто\\s+сделает","нужна\\s+помощь","посоветуйте","нужен\\s+исполнитель"]',
    '["заказать","помогите","ищу автора"]',
    '["мем","шутк","бесплатно"]',
    10.0,
    true
  ),
  (
    'urgent',
    'Срочность / дедлайн',
    '["срочно","горит","дедлайн","сдать\\s+завтра","до\\s+утра"]',
    '["срочно","успеть","сегодня"]',
    '["мем","шутк"]',
    12.0,
    true
  ),
  (
    'plagiarism',
    'Антиплагиат / уникальность',
    '["антиплагиат","уникальност","поднять\\s+уникальност"]',
    '["антиплаг","уникальность","проверка оригинальности"]',
    '[]',
    9.0,
    true
  ),
  (
    'formatting',
    'ГОСТ / оформление',
    '["гост","оформлен","список\\s+литератур","оформить\\s+вкр"]',
    '["ГОСТ","оформление","список литературы","ВКР"]',
    '[]',
    6.0,
    true
  ),
  (
    'revisions',
    'Правки по научруку / замечания',
    '["правк","замечани","научрук","исправит"]',
    '["правки","замечания","научный руководитель"]',
    '[]',
    7.0,
    true
  ),
  (
    'competitor_mention',
    'Упоминание конкурента',
    '["автор24","studwork","helpstudent","курсач"]',
    '[]',
    '[]',
    8.0,
    true
  )
ON CONFLICT (code) DO UPDATE
  SET
    description      = EXCLUDED.description,
    regex_patterns   = EXCLUDED.regex_patterns,
    keywords         = EXCLUDED.keywords,
    negative_keywords = EXCLUDED.negative_keywords,
    weight           = EXCLUDED.weight,
    enabled          = EXCLUDED.enabled,
    updated_at       = now();

-- ------------------------------------------------------------------ --
-- Default admin user (CHANGE PASSWORD before first production login) --
-- ------------------------------------------------------------------ --

-- Password hash is bcrypt of 'changeme_admin_2026' — replace immediately.
INSERT INTO users (email, role, password_hash)
VALUES (
  'admin@studyassist.local',
  'admin',
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMUd8VO5Oc5cJMOJGqN9e/5C6S'
)
ON CONFLICT (email) DO NOTHING;

INSERT INTO users (email, role, password_hash)
VALUES (
  'operator@studyassist.local',
  'operator',
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMUd8VO5Oc5cJMOJGqN9e/5C6S'
)
ON CONFLICT (email) DO NOTHING;
