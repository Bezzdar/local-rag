"""Реэкспорт всех Pydantic-схем API (обратная совместимость)."""
# --- Imports ---
from __future__ import annotations

from .chat import (  # noqa: F401
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Citation,
    CitationLocation,
)
from .common import now_iso  # noqa: F401
from .llm import IndexStatus  # noqa: F401
from .notebooks import (  # noqa: F401
    CreateNotebookRequest,
    Notebook,
    UpdateNotebookRequest,
)
from .notes import (  # noqa: F401
    CreateGlobalNoteRequest,
    GlobalNote,
    SaveCitationRequest,
    SavedCitation,
)
from .sources import (  # noqa: F401
    AddPathRequest,
    ParsingSettings,
    ReorderSourcesRequest,
    Source,
    UpdateSourceRequest,
)
