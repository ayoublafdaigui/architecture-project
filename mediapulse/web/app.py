import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
import asyncpg

logger = logging.getLogger(__name__)

app = FastAPI(title="MediaPulse News Viewer")

templates_path = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(
    loader=FileSystemLoader(templates_path),
    autoescape=select_autoescape(["html", "xml"]),
)

# Database connection settings from env (reuse same as core config)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "mediapulse")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mediapulse")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mediapulse")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Simple connection pool created at startup
@app.on_event("startup")
async def startup():
    app.state.pg_pool = await asyncpg.create_pool(DATABASE_URL)
    logger.info("PostgreSQL connection pool created for web UI")

@app.on_event("shutdown")
async def shutdown():
    await app.state.pg_pool.close()
    logger.info("PostgreSQL connection pool closed")

@app.get("/news", response_class=HTMLResponse)
async def view_news(request: Request, limit: int = 20):
    """Render a simple page with the most recent news articles.

    The query reads from the `bronze_articles` table – the raw layer where
    `mediapulse.ingestion.run_batch_scrape` stores validated `Article` objects.
    Adjust the table name if your schema differs.
    """
    async with app.state.pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT title, source, url, published_at, category, language
            FROM bronze_articles
            ORDER BY scraped_at DESC
            LIMIT $1
            """,
            limit,
        )
    # Transform asyncpg Record objects into plain dicts for the template
    articles = [dict(row) for row in rows]
    template = jinja_env.get_template("news.html")
    return template.render(request=request, articles=articles)
