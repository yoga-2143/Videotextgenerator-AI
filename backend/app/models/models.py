from datetime import datetime
from app import db
from sqlalchemy.dialects.mysql import LONGTEXT

LongText = db.Text().with_variant(LONGTEXT, "mysql")


from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255))
    password_hash = db.Column(db.String(255), nullable=True)
    picture_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    videos = db.relationship("Video", backref="user", lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Video(db.Model):
    __tablename__ = "videos"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    youtube_id = db.Column(db.String(20), nullable=False, index=True)
    youtube_url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(500))
    channel_name = db.Column(db.String(255))
    description = db.Column(db.Text)
    duration = db.Column(db.String(50))
    published_at_str = db.Column(db.String(100))
    thumbnail_url = db.Column(db.String(500))
    original_language = db.Column(db.String(10))
    transcript_source = db.Column(db.String(20))  # 'captions' or 'whisper'
    status = db.Column(db.String(20), default="pending")  # pending, processing, done, failed
    error_message = db.Column(db.Text)
    processing_error_code = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transcript = db.relationship("Transcript", backref="video", cascade="all, delete-orphan", uselist=False, lazy=True)
    articles = db.relationship("Article", backref="video", cascade="all, delete-orphan", lazy=True)


class Transcript(db.Model):
    __tablename__ = "transcripts"
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False, index=True)
    raw_text = db.Column(LongText)
    cleaned_text = db.Column(LongText)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Article(db.Model):
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False, index=True)
    language = db.Column(db.String(10), default="en", index=True)
    title = db.Column(db.String(500))
    content = db.Column(LongText)
    source_text_hash = db.Column(db.String(64), nullable=True, index=True)
    is_original = db.Column(db.Boolean, default=True)
    is_published = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime, nullable=True)
    qa_results = db.Column(db.Text, nullable=True)  # JSON-encoded QA badges & scores
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    audio = db.relationship("Audio", backref="article", cascade="all, delete-orphan", lazy=True)

    __table_args__ = (db.UniqueConstraint("video_id", "language", name="uq_video_language"),)


class Audio(db.Model):
    __tablename__ = "audio"
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False, index=True)
    language = db.Column(db.String(10), index=True)
    source_text_hash = db.Column(db.String(64), nullable=True, index=True)
    file_path = db.Column(db.String(500))
    dubbing_source = db.Column(db.String(50), default="gtts_fallback")  # seamless_m4t, gtts_fallback, none
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TranslationCache(db.Model):
    __tablename__ = "translation_cache"
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False, index=True)
    target_language = db.Column(db.String(10), nullable=False, index=True)
    source_text_hash = db.Column(db.String(64), nullable=True, index=True)
    title = db.Column(db.String(500))
    content = db.Column(LongText)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("article_id", "target_language", name="uq_article_target_lang"),)

