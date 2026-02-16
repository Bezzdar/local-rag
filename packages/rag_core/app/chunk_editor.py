import logging
import sys
from pathlib import Path
from typing import Dict
from uuid import uuid4

import streamlit as st

# ---------------------------------------------------------------------------
# Конфигурация путей
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# ---------------------------------------------------------------------------
# Внутренние импорты (после корректировки sys.path)
# ---------------------------------------------------------------------------
from app.engine import get_library_folders
from app.chunk_manager import (
    count_chunks_in_index,
    get_chunk_by_number,
    update_chunk_by_number,
    add_chunk_to_folder,
    delete_chunk_by_number,
)

# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def main() -> None:
    """Интерактивный редактор чанков ("ленивая" подгрузка)."""

    st.set_page_config(page_title="✂️ Редактор чанков", page_icon="✂️", layout="wide")
    st.title("✂️ Редактор чанков (ленивая подгрузка)")

    # --- Список папок -------------------------------------------------------
    folders = get_library_folders()
    if not folders:
        st.warning("Нет папок с документами.")
        st.stop()

    folder_to_edit: str = st.selectbox(
        "Папка с чанками для редактирования", folders, key="edit_folder_editor"
    )

    # --- Метаданные коллекции ----------------------------------------------
    n_chunks: int = count_chunks_in_index(folder_to_edit)
    st.write(f"🔎 Число чанков: {n_chunks}")
    if n_chunks == 0:
        st.info("В выбранной папке нет чанков.")
        st.stop()

    # -----------------------------------------------------------------------
    # Центральный чанк (номер от 1 .. n_chunks). Храним в session_state, чтобы
    # после st.experimental_rerun() позиция ленты сохранялась.
    # -----------------------------------------------------------------------
    central_key = f"central_idx_{folder_to_edit}"
    central_idx: int = st.session_state.get(central_key, 0)  # 0‑based

    user_input = st.number_input(
        "Номер центрального чанка:",
        min_value=1,
        max_value=n_chunks,
        value=central_idx + 1,
        step=1,
        key=f"num_input_{folder_to_edit}_{uuid4().hex}",
    )
    central_idx = int(user_input) - 1
    st.session_state[central_key] = central_idx

    # Окно отображения (±2 чанка вокруг центрального)
    idx_range = range(max(0, central_idx - 2), min(n_chunks, central_idx + 3))

    st.markdown("**Для копирования выделите текст и нажмите Ctrl+C.**")

    updated_chunks: Dict[int, Dict] = {}

    for real_idx in idx_range:
        chunk = get_chunk_by_number(folder_to_edit, real_idx + 1) or {"text": ""}
        default_text = chunk.get("text", "")
        new_text = st.text_area(
            label=f"Чанк {real_idx + 1}",
            value=default_text,
            height=200 if real_idx == central_idx else 120,
            key=f"chunk_{folder_to_edit}_{real_idx}_{uuid4().hex}",
        )
        if new_text != default_text:
            updated_chunks[real_idx + 1] = {"text": new_text}

    # -----------------------------------------------------------------------
    # Кнопки навигации и действий
    # -----------------------------------------------------------------------
    prev_col, next_col, add_col, del_col, save_col = st.columns(5)

    if prev_col.button("← Назад"):
        st.session_state[central_key] = max(0, central_idx - 1)
        st.experimental_rerun()

    if next_col.button("→ Вперёд"):
        st.session_state[central_key] = min(n_chunks - 1, central_idx + 1)
        st.experimental_rerun()

    if add_col.button("Добавить чанк"):
        add_chunk_to_folder(folder_to_edit, {"text": ""}, storage="chroma")
        st.success("Добавлен новый чанк.")
        st.experimental_rerun()

    if del_col.button("Удалить чанк"):
        delete_chunk_by_number(folder_to_edit, central_idx + 1, storage="chroma")
        st.success("Чанк удалён.")
        st.experimental_rerun()

    if save_col.button("💾 Сохранить изменения"):
        for number, body in updated_chunks.items():
            update_chunk_by_number(folder_to_edit, number, body, storage="chroma")
        st.success("Изменения сохранены.")


if __name__ == "__main__":
    main()
