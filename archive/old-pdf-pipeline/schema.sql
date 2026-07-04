-- ================================================================
-- CGSS 问卷资料库 — 数据库建表SQL
-- 适用: SQLite 3.x+
-- ================================================================

-- 1. 调查元信息
CREATE TABLE IF NOT EXISTS surveys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 简称: CGSS
    full_name TEXT,                      -- 全称: Chinese General Social Survey
    name_cn TEXT,                        -- 中文名: 中国综合社会调查
    institution TEXT,                    -- 执行机构
    website TEXT,                        -- 官网
    description TEXT                     -- 简介
);

-- 2. 波次
CREATE TABLE IF NOT EXISTS waves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id INTEGER NOT NULL REFERENCES surveys(id),
    year INTEGER NOT NULL,
    sample_size INTEGER,
    questionnaire_type TEXT DEFAULT '个人问卷',  -- 家庭问卷/个人问卷/村居问卷
    source_file TEXT,                    -- 原始文件名
    notes TEXT,
    UNIQUE(survey_id, year, questionnaire_type)
);

-- 3. 变量（核心表）
CREATE TABLE IF NOT EXISTS variables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wave_id INTEGER NOT NULL REFERENCES waves(id),
    var_name TEXT NOT NULL,              -- a1, a2, a3a
    section TEXT,                        -- A部分：核心模块
    question_number TEXT,                -- 题号: A1, A1a
    question_text TEXT NOT NULL,         -- 题干
    question_type TEXT,                  -- 单选题/多选题/填空题/开放题/量表题
    interviewer_note TEXT,               -- 访题说明
    skip_pattern TEXT,                   -- 跳转逻辑
    universe TEXT,                       -- 适用人群
    is_core_module INTEGER DEFAULT 0,    -- 是否核心追踪模块
    sort_order REAL                      -- 题号排序
);

-- 4. 值标签
CREATE TABLE IF NOT EXISTS value_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variable_id INTEGER NOT NULL REFERENCES variables(id),
    value TEXT NOT NULL,                 -- 编码: 1, 2, 97
    label TEXT NOT NULL,                 -- 标签: 男, 女, 不适用
    is_missing INTEGER DEFAULT 0,        -- 是否系统缺失
    sort_order INTEGER DEFAULT 0
);

-- 5. 跨波次变量对照（后续扩展用）
CREATE TABLE IF NOT EXISTS crosswalk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id INTEGER REFERENCES surveys(id),
    var_name TEXT,
    wave_a_id INTEGER REFERENCES waves(id),
    wave_b_id INTEGER REFERENCES waves(id),
    variable_a_id INTEGER REFERENCES variables(id),
    variable_b_id INTEGER REFERENCES variables(id),
    match_type TEXT,                     -- exact / similar / derived
    note TEXT
);

-- ================================================================
-- FTS5 全文搜索
-- ================================================================
CREATE VIRTUAL TABLE IF NOT EXISTS variables_fts USING fts5(
    var_name,
    question_text,
    section,
    content='variables',
    content_rowid='id'
);

-- ================================================================
-- 索引
-- ================================================================
CREATE INDEX IF NOT EXISTS idx_variables_wave ON variables(wave_id);
CREATE INDEX IF NOT EXISTS idx_variables_name ON variables(var_name);
CREATE INDEX IF NOT EXISTS idx_variables_section ON variables(section);
CREATE INDEX IF NOT EXISTS idx_value_labels_var ON value_labels(variable_id);
CREATE INDEX IF NOT EXISTS idx_waves_survey_year ON waves(survey_id, year);

-- ================================================================
-- 触发器：variables增删改时自动同步FTS5
-- ================================================================
CREATE TRIGGER IF NOT EXISTS variables_ai AFTER INSERT ON variables BEGIN
    INSERT INTO variables_fts(rowid, var_name, question_text, section)
    VALUES (new.id, new.var_name, new.question_text, new.section);
END;

CREATE TRIGGER IF NOT EXISTS variables_ad AFTER DELETE ON variables BEGIN
    INSERT INTO variables_fts(variables_fts, rowid, var_name, question_text, section)
    VALUES ('delete', old.id, old.var_name, old.question_text, old.section);
END;

CREATE TRIGGER IF NOT EXISTS variables_au AFTER UPDATE ON variables BEGIN
    INSERT INTO variables_fts(variables_fts, rowid, var_name, question_text, section)
    VALUES ('delete', old.id, old.var_name, old.question_text, old.section);
    INSERT INTO variables_fts(rowid, var_name, question_text, section)
    VALUES (new.id, new.var_name, new.question_text, new.section);
END;
