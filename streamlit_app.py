import os
import logging
from typing import List

import streamlit as st
import requests

# ----------------- ENV & LOGGING -------------------------------------------
#   • Отключаем «глючный» file‑watcher Streamlit ↦ устраняем warning
#   • Собираем минимальный логгер вместо print() для дальнейшей отладки
# ---------------------------------------------------------------------------
os.environ.setdefault("STREAMLIT_FILE_WATCHER_TYPE", "none")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s %(message)s",
)
logger = logging.getLogger(__name__)

# ----------------- APP IMPORTS ---------------------------------------------
#  Внешние модули проекта. Расположение путей лучше вынести в PYTHONPATH, но
#  здесь оставляем прямой импорт.
# ---------------------------------------------------------------------------
from app.engine import (
    get_library_folders, list_documents_for_folder, check_indexed_files,
    trigger_indexing
)
from app.llm_generic import ask_llm
from app.user_settings import (
    get_active_analytical_model, set_active_analytical_model,
    get_active_math_model, set_active_math_model,
    get_analytical_server_url, set_analytical_server_url,
    get_math_server_url, set_math_server_url,
    get_share_library, set_share_library,
    get_library_port, set_library_port,
)
from app.search_engine import (
    llm_generate_query, run_fast_search, llm_summarize_chunks,
)
from app.math_engine import run_python_code
from app.chunk_manager import (
    get_chunks_for_folder, count_chunks_in_index, get_chunk_by_number,
    ChunkStore,
)

# ----------------- UTILS ----------------------------------------------------
#  CPU‑и/IO‑heavy вычисления/чтения кешируем через Streamlit cache. Функции
#  ниже возвращают неизменяемые (для нашего цикла) объекты, поэтому safe.
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cached_library_folders() -> List[str]:
    return get_library_folders()

@st.cache_data(show_spinner=False)
def cached_count_chunks(folder: str) -> int:
    return count_chunks_in_index(folder)

@st.cache_data(show_spinner=False)
def cached_chunks_for_folder(folder: str) -> list[dict]:
    return get_chunks_for_folder(folder)

@st.cache_data(show_spinner=False)
def cached_chunks_for_folders(folders: tuple[str, ...]) -> list[dict]:
    return [ch for folder in folders for ch in cached_chunks_for_folder(folder)]


def _normalize_url_from_port(raw: str, fallback: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return fallback
    if raw.isdigit():
        return f"http://127.0.0.1:{int(raw)}"
    return raw


def _probe_llm_server(url: str) -> tuple[str, str]:
    base = url.rstrip("/")
    try:
        ping = requests.get(base + "/version", timeout=2)
        if ping.status_code == 200:
            return "success", "llama.cpp"
    except Exception:
        pass

    try:
        ping = requests.get(base + "/api/tags", timeout=2)
        if ping.status_code == 200:
            return "success", "ollama"
        return "warning", "unknown"
    except Exception as exc:
        return "error", str(exc)

# ----------------- STREAMLIT CONFIG ----------------------------------------
st.set_page_config(page_title="RAG Ассистент", layout="wide")

# ----------------- SIDEBAR --------------------------------------------------
with st.sidebar:
    st.title("Навигация")
    tab = st.radio(
        "Выберите раздел",
        [
            "Обработка документов",
            "Библиотека",
            "Редактор чанков",
            "Математика",
            "Шаблоны отчетов",
            "Настройки",
        ],
    )
    st.markdown("---")

    rag_mode = st.checkbox(
        "Работа с документами (RAG-режим)",
        value=True,
        help=(
            "В этом режиме ИИ ищет ответ только в подключённых папках. "
            "Если выключено — работает как обычный чат."
        ),
    )
    st.session_state["rag_mode"] = rag_mode

    st.subheader("📚 Библиотека документов")
    folders = cached_library_folders()

    if not folders:
        st.info("Нет ни одной папки библиотеки. Добавьте папки с файлами в data/docs.")
        selected_folders: List[str] = []
    else:
        selected_folders = st.multiselect(
            "Активные папки для анализа (RAG)",
            folders,
            default=folders,
            key="active_library_folders",
        )

# =============== ОБРАБОТКА ДОКУМЕНТОВ =======================================
if tab == "Обработка документов":
    st.header("📑 Обработка документов и чанк-менеджмент")

    # --- Session‑level singletons -----------------------------------------
    if "chunk_store" not in st.session_state:
        st.session_state.chunk_store = ChunkStore()
    if "doc_chat_history" not in st.session_state:
        st.session_state.doc_chat_history = []

    chunk_store: ChunkStore = st.session_state.chunk_store

    # --- Layout -----------------------------------------------------------
    col1, col2, col3 = st.columns([1.3, 2, 1.3])

    # ----------- COL 1: текущие чанки ------------------------------------
    with col1:
        st.subheader("Чанки (фрагменты для анализа)")
        if st.button("Очистить базу чанков"):
            chunk_store.clear()
            st.session_state.doc_chat_history = []
            st.success("Чанки и история чата очищены.")

        rows = chunk_store.as_display()
        st.markdown(f"**Всего чанков:** {len(rows)}")
        for idx, (text, ref) in enumerate(rows):
            st.markdown(f"**{idx + 1}.** {text}")
            st.markdown(ref)
            # уникальный ключ кнопки, чтобы избежать clash
            if st.button("Удалить", key=f"del_chunk_{idx}"):
                chunk_store.remove_by_idx(idx)
                st.rerun()

    # ----------- COL 2: история диалога ----------------------------------
    with col2:
        st.subheader("История чата (любой поиск)")
        for msg in st.session_state.doc_chat_history:
            role, content = msg["role"], msg["content"]
            if role == "user":
                st.markdown(
                    f"<div style='color:#3366cc'><b>Вы:</b> {content}</div>",
                    unsafe_allow_html=True,
                )
            elif role == "system":
                st.markdown(
                    f"<div style='color:#999'><b>Служебное:</b> {content}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='color:#444'><b>ИИ:</b> {content}</div>",
                    unsafe_allow_html=True,
                )
        st.divider()

    # ----------- COL 3: поиск / анализ -----------------------------------
    with col3:
        st.subheader("Поиск по библиотеке")

        # === ИИ‑поиск (RAG + LLM) =======================================
        st.markdown("**ИИ‑поиск по всей библиотеке**")
        user_prompt = st.text_input("Запрос для ИИ‑поиска", key="rag_llm_query")

        if st.button("ИИ‑поиск") and user_prompt.strip():
            folders = st.session_state.get("active_library_folders", [])

            all_chunks = (
                cached_chunks_for_folders(tuple(sorted(folders))) if folders else chunk_store.chunks
            )
            query, log_string = llm_generate_query(user_prompt)

            st.session_state.doc_chat_history.extend(
                [
                    {"role": "user", "content": user_prompt},
                    {"role": "system", "content": f"[LLM-Query]: {log_string}"},
                ]
            )

            found_chunks = run_fast_search(query, all_chunks)
            chunk_store.add_unique(found_chunks)
            st.success(f"В стек добавлено {len(found_chunks)} новых чанков")

            summary = llm_summarize_chunks(found_chunks, user_prompt)
            st.session_state.doc_chat_history.append({"role": "assistant", "content": summary})

            if found_chunks:
                evidence = "\n".join(
                    [f"{idx + 1}. {ch.get('text', '')[:200]}..." for idx, ch in enumerate(found_chunks[:5])]
                )
                st.session_state.doc_chat_history.append(
                    {"role": "system", "content": f"**Опорные чанки:**\n{evidence}"}
                )
            st.rerun()

        st.divider()

        # === ИИ‑анализ выбранных чанков ==================================
        st.markdown("**ИИ‑анализ выбранных чанков**")
        with st.form(key="doc_chat_form", clear_on_submit=True):
            user_prompt_manual = st.text_area("Сообщение", height=80, key="doc_chat_input")
            submitted = st.form_submit_button("Анализировать выбранные чанки")

            if submitted and user_prompt_manual.strip():
                st.session_state.doc_chat_history.append({
                    "role": "user", "content": user_prompt_manual.strip(),
                })

                chunk_texts = [ch["text"] for ch in chunk_store.chunks]
                if chunk_texts:
                    context = "\n\n".join(f"- {chunk.strip()}" for chunk in chunk_texts)
                    prompt = (
                        "Используй только факты из этих выбранных фрагментов для ответа на вопрос.\n"
                        f"Фрагменты:\n{context}\n\n"
                        f"Вопрос пользователя: {user_prompt_manual.strip()}\n\n"
                        "Сделай ответ максимально точным и опирайся только на эти фрагменты."
                    )
                else:
                    prompt = user_prompt_manual.strip()

                analytical_url = get_analytical_server_url()
                analytical_model = get_active_analytical_model()
                answer = ask_llm(prompt, model=analytical_model, server_url=analytical_url)
                st.session_state.doc_chat_history.append({"role": "assistant", "content": answer})

        st.divider()

        # === Ручной поиск (TF‑IDF / AND / NOT) ===========================
        st.markdown("**Ручной поиск по библиотеке (TF‑IDF/AND/NOT)**")
        search_query = st.text_input("Поиск по документам", key="doc_search_query")
        col_search, col_and, col_not = st.columns(3)

        if col_search.button("Поиск") and search_query.strip():
            folders = st.session_state.get("active_library_folders", [])
            found = [
                ch
                for folder in folders
                for ch in cached_chunks_for_folder(folder)
                if search_query.lower() in ch["text"].lower()
            ]
            chunk_store.add_unique(found)
            st.session_state.doc_chat_history.append({"role": "system", "content": f"[TF-IDF]: {search_query}"})
            st.rerun()

        if col_and.button("AND") and search_query.strip():
            chunk_store.filter_by_query(search_query, mode="and")
            st.session_state.doc_chat_history.append({"role": "system", "content": f"[AND]: {search_query}"})
            st.rerun()

        if col_not.button("NOT") and search_query.strip():
            chunk_store.filter_by_query(search_query, mode="not")
            st.session_state.doc_chat_history.append({"role": "system", "content": f"[NOT]: {search_query}"})
            st.rerun()

# =============== БИБЛИОТЕКА ================================================
elif tab == "Библиотека":
    st.header("📚 Библиотека документов")
    folders = cached_library_folders()

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("Состояние файлов")
        if not folders:
            st.info("Нет ни одной папки библиотеки.")
        else:
            for folder in folders:
                st.markdown(f"**{folder}**")
                files = list_documents_for_folder(folder)
                indexed_files = check_indexed_files(folder)
                for file in files:
                    indexed = indexed_files.get(file, False) if isinstance(indexed_files, dict) else False
                    color = "green" if indexed else "blue"
                    label = (
                        f"🟩 {file} (проиндексировано)" if indexed else f"🟦 {file} (не проиндексировано)"
                    )
                    st.markdown(f"<span style='color:{color}'>{label}</span>", unsafe_allow_html=True)

    with col_right:
        st.subheader("Управление")
        if not folders:
            st.warning("Нет папок с документами для индексации.")
        else:
            folder_to_view = st.selectbox("Папка для просмотра", folders)

            if st.button("Индексировать выбранную папку"):
                trigger_indexing(folder_to_view)
                cached_count_chunks.clear()
                cached_chunks_for_folder.clear()
                cached_chunks_for_folders.clear()
                st.success(f"Папка «{folder_to_view}» отправлена на индексацию.")

            if st.button("Индексировать все папки"):
                for folder in folders:
                    trigger_indexing(folder)
                cached_count_chunks.clear()
                cached_chunks_for_folder.clear()
                cached_chunks_for_folders.clear()
                st.success("Индексация всех папок запущена.")

            st.markdown("Проверка чанков:")
            num_chunks = cached_count_chunks(folder_to_view)
            st.markdown(f"**Кол-во чанков в папке:** {num_chunks}")

            chunk_num = st.number_input(
                "Номер чанка для просмотра",
                min_value=1,
                max_value=max(num_chunks, 1),
                value=1,
                step=1,
                key=f"chunknum_{folder_to_view}",
            )

            if st.button("Показать чанк", key=f"showchunk_{folder_to_view}"):
                chunk = get_chunk_by_number(folder_to_view, int(chunk_num))
                if chunk:
                    st.text_area(
                        "Текст выбранного чанка",
                        chunk["text"],
                        height=200,
                        key=f"outchunk_{folder_to_view}",
                    )
                else:
                    st.warning("Нет такого чанка!")

# =============== РЕДАКТОР ЧАНКОВ ===========================================
#   (оставлен без изменений, кроме проверки на пустую библиотеку и мелких UI‑fix)
# ---------------------------------------------------------------------------
elif tab == "Редактор чанков":
    st.header("✂️ Редактор чанков")
    folders = cached_library_folders()

    if not folders:
        st.warning("Нет папок с документами.")
    else:
        from app.chunk_manager import (
            count_chunks_in_index,
            get_chunk_by_number,
            update_chunk_by_number,
            add_chunk_to_folder,
            delete_chunk_by_number,
        )

        folder_to_edit = st.selectbox("Папка с чанками для редактирования", folders, key="edit_folder")
        n_chunks = cached_count_chunks(folder_to_edit)
        if n_chunks == 0:
            st.info("В выбранной папке нет чанков.")
        else:
            key_central = f"editor_chunk_num_{folder_to_edit}"
            st.session_state.setdefault(key_central, 1)

            central_idx = (
                st.number_input(
                    "Номер чанка (центр ленты)",
                    min_value=1,
                    max_value=n_chunks,
                    value=st.session_state[key_central],
                    step=1,
                    key=f"n_central_{folder_to_edit}",
                )
                - 1
            )
            st.session_state[key_central] = central_idx + 1

            idx_range = range(max(0, central_idx - 2), min(n_chunks, central_idx + 3))
            chunks_window = [
                get_chunk_by_number(folder_to_edit, idx + 1) or {"text": ""} for idx in idx_range
            ]

            st.write("**Для копирования: выделите текст и Ctrl+C/Ctrl+V.**")

            updated_chunks = {}
            for win_idx, chunk in enumerate(chunks_window):
                real_idx = idx_range[win_idx]
                key = f"edit_chunk_{folder_to_edit}_{real_idx}"
                val = str(chunk.get("text", ""))
                height = 200 if real_idx == central_idx else 120

                def _render_area(bg_color: str | None = None):
                    if bg_color:
                        st.markdown(
                            f'<div style="background-color:{bg_color};padding:8px;border-radius:8px;">',
                            unsafe_allow_html=True,
                        )
                    new_val = st.text_area(
                        f"Чанк {real_idx + 1}{' (Центральный)' if real_idx == central_idx else ''}:",
                        value=val,
                        height=height,
                        key=key,
                    )
                    if bg_color:
                        st.markdown("</div>", unsafe_allow_html=True)
                    return new_val

                if real_idx == central_idx:
                    new_val = _render_area("#f7e7b7")  # yellow
                elif real_idx == central_idx + 1:
                    new_val = _render_area("#d0e7ff")  # blue
                else:
                    new_val = _render_area()

                if new_val != val:
                    chunk["text"] = new_val
                    updated_chunks[real_idx + 1] = chunk

            col1, col2, col3, col4, col5 = st.columns(5)
            if col1.button("← Назад", key=f"btn_prev_{folder_to_edit}"):
                st.session_state[key_central] = max(1, central_idx)
                st.rerun()
            if col2.button("→ Вперёд", key=f"btn_next_{folder_to_edit}"):
                st.session_state[key_central] = min(n_chunks, central_idx + 2)
                st.rerun()
            if col3.button("Добавить чанк", key=f"btn_add_{folder_to_edit}"):
                add_chunk_to_folder(folder_to_edit, {"text": ""}, storage="chroma")
                st.success("Добавлен новый чанк.")
                st.rerun()
            if col4.button("Удалить чанк", key=f"btn_del_{folder_to_edit}"):
                delete_chunk_by_number(folder_to_edit, central_idx + 1, storage="chroma")
                st.success("Чанк удалён.")
                st.rerun()
            if col5.button("Сохранить", key=f"btn_save_{folder_to_edit}"):
                for number, ch in updated_chunks.items():
                    update_chunk_by_number(folder_to_edit, number, ch, storage="chroma")
                st.success("Изменения сохранены.")

# =============== МАТЕМАТИКА =================================================
elif tab == "Математика":
    st.header("🧮 Математический ассистент (LLM + Python)")
    st.markdown("Опиши математическую задачу или загрузи файл — ИИ сгенерирует и выполнит код!")

    math_prompt = st.text_area("Текст запроса или пояснение", height=80)
    uploaded_files = st.file_uploader(
        "Файлы (опционально, .csv/.xlsx/.txt)", accept_multiple_files=True
    )
    files_dict = {f.name: f.read() for f in uploaded_files} if uploaded_files else {}

    if st.button("Сгенерировать и выполнить код"):
        if not math_prompt.strip():
            st.warning("Введите математический запрос.")
        else:
            # FIXME: заменить заглушку на обращение к math‑LLM
            code = (
                "import numpy as np\n"
                "x = np.linspace(0, 10, 100)\n"
                "y = np.sin(x)\n"
                "import matplotlib.pyplot as plt\n"
                "plt.plot(x, y)\n"
                "plt.title('График sin(x)')\n"
                "plt.xlabel('x')\n"
                "plt.ylabel('sin(x)')\n"
                "plt.grid()\n"
                "plt.show()\n"
                "print('Максимум синуса:', max(y))\n"
            )
            st.code(code, language="python")
            with st.spinner("Выполняется код..."):
                output, error, images = run_python_code(code, files=files_dict)
            if output:
                st.success(f"Stdout:\n{output}")
            if error:
                st.error(f"Stderr:\n{error}")
            for idx, img in enumerate(images):
                st.image(img, caption=f"График #{idx + 1}", use_column_width=True)

# =============== ШАБЛОНЫ ОТЧЁТОВ ===========================================
elif tab == "Шаблоны отчетов":
    st.header("📄 Шаблоны отчетов")
    st.markdown("**Выберите шаблон для генерации отчёта (функционал в разработке):**")
    cols = st.columns(3)
    for i in range(6):
        with cols[i % 3]:
            st.button(f"Шаблон {i + 1}", key=f"template_{i + 1}")

# =============== НАСТРОЙКИ ==================================================
elif tab == "Настройки":
    st.header("⚙️ Настройки LLM")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Аналитическая модель**")
        analytical_url = st.text_input(
            "Адрес сервера (аналитика) или порт Ollama",
            get_analytical_server_url(),
            key="analytical_url",
            help="Можно указать полный URL (http://host:port) или только порт, например 11434.",
        )
        analytical_url = _normalize_url_from_port(analytical_url, get_analytical_server_url())
        set_analytical_server_url(analytical_url)

        analytical_model = st.text_input(
            "Имя модели (аналитика)",
            get_active_analytical_model(),
            key="analytical_model_name",
            help="Для Ollama укажите тег модели, например llama3.1:8b или qwen2.5:7b.",
        )
        set_active_analytical_model(analytical_model.strip())

        status, detail = _probe_llm_server(analytical_url)
        if status == "success":
            st.success(f"🟢 Сервер онлайн ({detail}): {analytical_url}")
        elif status == "warning":
            st.warning(f"⚠️ Сервер отвечает, но тип API не распознан: {analytical_url}")
        else:
            st.error(f"🔴 Сервер не отвечает: {analytical_url} ({detail})")

    with col2:
        st.markdown("**Математическая модель**")
        math_url = st.text_input(
            "Адрес сервера (математика) или порт Ollama",
            get_math_server_url(),
            key="math_url",
            help="Можно указать полный URL (http://host:port) или только порт, например 11434.",
        )
        math_url = _normalize_url_from_port(math_url, get_math_server_url())
        set_math_server_url(math_url)

        math_model = st.text_input(
            "Имя модели (математика)",
            get_active_math_model(),
            key="math_model_name",
            help="Для Ollama укажите тег модели, например deepseek-coder:6.7b.",
        )
        set_active_math_model(math_model.strip())

        status, detail = _probe_llm_server(math_url)
        if status == "success":
            st.success(f"🟢 Сервер онлайн ({detail}): {math_url}")
        elif status == "warning":
            st.warning(f"⚠️ Сервер отвечает, но тип API не распознан: {math_url}")
        else:
            st.error(f"🔴 Сервер не отвечает: {math_url} ({detail})")

    st.caption("Подсказка: для Ollama обычно используется порт 11434. Можно ввести только `11434`.")
    st.markdown("---")

    # ---- Тестовый чат ----------------------------------------------------
    st.session_state.setdefault("test_chat_history", [])

    with st.container():
        st.markdown("#### История чата")
        for msg in st.session_state.test_chat_history:
            role, content = msg.get("role", "user"), msg.get("content", "")
            color = "#3366cc" if role == "user" else "#444"
            label = "Вы" if role == "user" else "ИИ"
            st.markdown(
                f"<div style='color:{color}'><b>{label}:</b> {content}</div>",
                unsafe_allow_html=True,
            )
        st.divider()

    with st.form(key="test_chat_form", clear_on_submit=True):
        user_prompt = st.text_area("Сообщение для теста модели", height=80, key="test_chat_input")
        test_targets = {
            "Аналитическая модель": (get_analytical_server_url(), get_active_analytical_model()),
            "Математическая модель": (get_math_server_url(), get_active_math_model()),
        }
        target_name = st.selectbox("Куда отправить тестовый запрос:", list(test_targets.keys()), key="test_model_target")
        submitted = st.form_submit_button("Отправить")
        if submitted and user_prompt.strip():
            st.session_state.test_chat_history.append({"role": "user", "content": user_prompt.strip()})
            with st.spinner("Генерируется ответ..."):
                url, model = test_targets[target_name]
                answer = ask_llm(user_prompt.strip(), model=model, server_url=url)
            st.session_state.test_chat_history.append({"role": "assistant", "content": answer})
            st.rerun()

    st.markdown("---")
    col_port, col_share = st.columns(2)
    with col_port:
        port = st.number_input(
            "Порт трансляции библиотеки",
            min_value=1024,
            max_value=65535,
            value=get_library_port(),
            step=1,
        )
        set_library_port(int(port))
    with col_share:
        share = st.checkbox(
            "Трансляция библиотеки в локальной сети", value=get_share_library(), key="share_library"
        )
        set_share_library(share)
        if share:
            st.success(f"Ваша библиотека доступна по локальной сети (порт: {port}).")
        else:
            st.info("Трансляция библиотеки отключена.")
