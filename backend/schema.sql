-- VETRI database schema (also auto-created by SQLAlchemy on first run,
-- kept here for reference / manual setup).

CREATE DATABASE IF NOT EXISTS vetri_db CHARACTER SET utf8mb4;
USE vetri_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    google_id VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    picture_url VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_google_id (google_id)
);

CREATE TABLE IF NOT EXISTS videos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    youtube_id VARCHAR(20) NOT NULL,
    youtube_url VARCHAR(500) NOT NULL,
    title VARCHAR(500),
    thumbnail_url VARCHAR(500),
    original_language VARCHAR(10),
    transcript_source VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_youtube_id (youtube_id),
    INDEX idx_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    video_id INT NOT NULL,
    raw_text LONGTEXT,
    cleaned_text LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    INDEX idx_transcript_video (video_id)
);

CREATE TABLE IF NOT EXISTS articles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    video_id INT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    title VARCHAR(500),
    content LONGTEXT,
    source_text_hash VARCHAR(64),
    is_original BOOLEAN DEFAULT TRUE,
    is_published BOOLEAN DEFAULT FALSE,
    published_at DATETIME,
    qa_results TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    UNIQUE KEY uq_video_language (video_id, language),
    INDEX idx_article_language (language)
);

CREATE TABLE IF NOT EXISTS audio (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT NOT NULL,
    language VARCHAR(10),
    source_text_hash VARCHAR(64),
    file_path VARCHAR(500),
    dubbing_source VARCHAR(50) DEFAULT 'gtts_fallback',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    INDEX idx_audio_article (article_id)
);

CREATE TABLE IF NOT EXISTS translation_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    source_text_hash VARCHAR(64),
    title VARCHAR(500),
    content LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    UNIQUE KEY uq_article_target_lang (article_id, target_language),
    INDEX idx_target_language (target_language)
);

