CREATE DATABASE IF NOT EXISTS llm_project DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE llm_project;

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'student',
    current_quiz_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS login_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL,
    login_time DATETIME NOT NULL,
    INDEX idx_login_username (username),
    INDEX idx_login_time (login_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS custom_courses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    course_name VARCHAR(128) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS custom_questions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    category VARCHAR(128) NOT NULL,
    content TEXT NOT NULL,
    answer VARCHAR(255),
    solution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_question_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS study_sessions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL,
    course_name VARCHAR(128) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    duration_seconds INT,
    INDEX idx_study_username (username),
    INDEX idx_study_course (course_name),
    INDEX idx_study_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS interaction_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    question_id INT NOT NULL,
    student_id VARCHAR(64) NOT NULL,
    user_query TEXT NOT NULL,
    ai_response MEDIUMTEXT NOT NULL,
    is_leaking_answer TINYINT NOT NULL DEFAULT 0,
    leakage_score INT NOT NULL DEFAULT 0,
    rewrite_count INT NOT NULL DEFAULT 0,
    leakage_reason VARCHAR(255),
    hint_strength VARCHAR(32),
    pedagogical_intent VARCHAR(64),
    hint_safety_status VARCHAR(64),
    created_at DATETIME NOT NULL,
    INDEX idx_interaction_student (student_id),
    INDEX idx_interaction_question (question_id),
    INDEX idx_interaction_created_at (created_at),
    INDEX idx_interaction_leakage (is_leaking_answer, leakage_score),
    INDEX idx_interaction_hint_strength (hint_strength),
    INDEX idx_interaction_pedagogical_intent (pedagogical_intent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS system_configs (
    config_key VARCHAR(128) PRIMARY KEY,
    config_value MEDIUMTEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO custom_courses (course_name, description)
VALUES
    ('高等数学', '包含极限、导数、微积分等核心考点，重点测试逻辑推导能力。'),
    ('线性代数', '包含矩阵运算、特征值、二次型等，培养空间与代数转换思维。'),
    ('概率统计', '包含随机变量、分布规律、信息熵等，结合实际应用场景。'),
    ('C语言', '包含指针、数组、结构体等核心语法，锻炼底层逻辑与编程思维。')
ON DUPLICATE KEY UPDATE description = VALUES(description);
