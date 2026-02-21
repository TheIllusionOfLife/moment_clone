"""Stage 2 — RAG: embed query and retrieve cooking principles via pgvector.

Returns top-3 cooking principles from the knowledge base and the last 5 session
summaries from LearnerState for use by downstream coaching stages.
"""

from google import genai
from sqlmodel import Session as DBSession
from sqlmodel import text

from backend.core.database import get_engine
from backend.core.settings import settings
from pipeline.stages.db_helpers import get_or_create_learner_state, get_session_with_dish


def run_rag(session_id: int) -> dict:
    """Retrieve relevant cooking principles and past session context for a session.

    Returns:
        {
            "principles": [str, ...],        # top-3 from pgvector similarity search
            "session_summaries": [dict, ...], # last 5 from LearnerState
        }
    """
    session, dish = get_session_with_dish(session_id)

    # Build query text from video diagnosis + dish principles
    query_parts: list[str] = []
    if session.video_analysis and session.video_analysis.get("diagnosis"):
        query_parts.append(session.video_analysis["diagnosis"])
    if dish.principles:
        query_parts.append(" ".join(str(p) for p in dish.principles))
    query_text = " ".join(query_parts) if query_parts else dish.name_ja

    # Embed the query via Gemini
    gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    result = gemini_client.models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=query_text,
    )
    assert result.embeddings, "Gemini embed_content returned no embeddings"
    embedding = result.embeddings[0].values  # list of floats

    # pgvector similarity search — must use raw SQL (SQLite in tests mocks this)
    sql = text(
        "SELECT principle_text FROM cooking_principles "
        "ORDER BY embedding <=> CAST(:vec AS vector) LIMIT 3"
    )
    with DBSession(get_engine()) as db:
        rows = db.execute(sql, {"vec": str(embedding)}).fetchall()
    principles = [row[0] for row in rows]

    # Load last 5 session summaries from LearnerState
    with DBSession(get_engine()) as db:
        ls = get_or_create_learner_state(session.user_id, db)
        session_summaries = (ls.session_summaries or [])[-5:]

    return {"principles": principles, "session_summaries": session_summaries}
