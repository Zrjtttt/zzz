import glob
import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.enricher import run_enrichment as run_enrichment_ollama
from src.enricher_openrouter import run_enrichment_openrouter
from src.parser_logic import run_full_parse
from src.rtf_loader import fetch_and_parse_law


VERSIONS_DIR = Path("data/versions")
PROCESSED_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")


st.set_page_config(
    page_title="Legal AI",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ Legal AI: Анализ и сравнение законов")


def initialize_session_state():
    if "openrouter_key" not in st.session_state:
        st.session_state.openrouter_key = ""

    if "model_choice" not in st.session_state:
        st.session_state.model_choice = "Ollama (локально)"

    if "last_loaded_version" not in st.session_state:
        st.session_state.last_loaded_version = None

    if "compare_data" not in st.session_state:
        st.session_state.compare_data = None


def get_available_versions():
    """Возвращает список редакций в формате YYYYMMDD."""
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

    versions = []

    for path in VERSIONS_DIR.glob("*.json"):
        date_str = path.stem

        try:
            datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            continue

        versions.append(date_str)

    return sorted(set(versions), reverse=True)


def format_version(version):
    """Преобразует YYYYMMDD в YYYY-MM-DD."""
    if len(version) == 8:
        return f"{version[:4]}-{version[4:6]}-{version[6:8]}"

    return version


def load_version(version):
    """Загружает JSON выбранной редакции."""
    version_path = VERSIONS_DIR / f"{version}.json"

    if not version_path.exists():
        raise FileNotFoundError(
            f"Файл редакции не найден: {version_path}"
        )

    with version_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Файл редакции должен содержать JSON-объект.")

    articles = data.get("articles")

    if not isinstance(articles, list):
        raise ValueError(
            "В файле редакции отсутствует массив 'articles'."
        )

    return data


def article_matches(article, query):
    """Проверяет, соответствует ли статья поисковому запросу."""
    query = query.strip().lower()

    if not query:
        return True

    article_number = str(article.get("article", "")).lower()
    title = str(article.get("title", "")).lower()
    full_text = str(article.get("full_article_text", "")).lower()

    points_text = " ".join(
        str(point.get("text", ""))
        for point in article.get("points", [])
        if isinstance(point, dict)
    ).lower()

    return (
        query in article_number
        or query in title
        or query in full_text
        or query in points_text
    )


def article_sort_key(article):
    """Сортировка статей по номеру."""
    article_number = str(article.get("article", "")).strip()

    try:
        return (0, float(article_number))
    except ValueError:
        return (1, article_number)


def render_model_settings():
    st.sidebar.header("Настройки ИИ")

    model_choice = st.sidebar.selectbox(
        "Выберите модель для анализа:",
        (
            "Ollama (локально)",
            "DeepSeek через OpenRouter",
        ),
        index=(
            0
            if st.session_state.model_choice == "Ollama (локально)"
            else 1
        ),
        key="model_selector",
    )

    st.session_state.model_choice = model_choice

    if model_choice == "DeepSeek через OpenRouter":
        st.sidebar.header("🔑 API-ключ OpenRouter")

        api_key_input = st.sidebar.text_input(
            "Введите ваш ключ OpenRouter:",
            type="password",
            value=st.session_state.openrouter_key,
            help=(
                "Ключ используется только во время текущей сессии "
                "и не сохраняется в проект."
            ),
            key="openrouter_key_input",
        )

        if api_key_input:
            st.session_state.openrouter_key = api_key_input
            os.environ["OPENROUTER_API_KEY"] = api_key_input
        elif st.session_state.openrouter_key:
            os.environ["OPENROUTER_API_KEY"] = (
                st.session_state.openrouter_key
            )


def render_version_sidebar():
    st.sidebar.header("📚 Редакции 115-ФЗ")

    if st.sidebar.button(
        "🔄 Обновить закон из официального источника",
        key="update_law_button",
    ):
        with st.spinner("Скачивание и парсинг редакции..."):
            try:
                json_path = fetch_and_parse_law()

                if not json_path:
                    st.sidebar.error(
                        "Загрузчик не вернул путь к файлу."
                    )
                else:
                    json_path = Path(json_path)

                    if not json_path.exists():
                        st.sidebar.error(
                            f"Файл не найден после загрузки: {json_path}"
                        )
                    else:
                        loaded_version = json_path.stem
                        st.session_state.last_loaded_version = (
                            loaded_version
                        )

                        st.sidebar.success(
                            "✅ Закон успешно загружен."
                        )

                        st.rerun()

            except Exception as exc:
                st.sidebar.error(
                    f"Ошибка загрузки редакции: {exc}"
                )

    versions = get_available_versions()

    if not versions:
        st.sidebar.warning(
            "Нет сохранённых редакций. "
            "Нажмите «Обновить закон»."
        )

        return versions, None, None

    last_loaded_version = st.session_state.get("last_loaded_version")

    if last_loaded_version in versions:
        default_index = versions.index(last_loaded_version)
    else:
        default_index = 0

    selected_version = st.sidebar.selectbox(
        "Выберите редакцию для просмотра:",
        versions,
        index=default_index,
        format_func=format_version,
        key="selected_version",
    )

    try:
        law_data = load_version(selected_version)
        article_count = len(law_data.get("articles", []))

        st.sidebar.info(
            f"Редакция: {format_version(selected_version)}\n\n"
            f"Статей: {article_count}"
        )

        if last_loaded_version == selected_version:
            st.sidebar.success(
                "Последняя загруженная редакция"
            )

        return versions, selected_version, law_data

    except Exception as exc:
        st.sidebar.error(
            f"Ошибка чтения редакции: {exc}"
        )

        return versions, selected_version, None


def render_version_view(selected_version, law_data):
    if not selected_version or not law_data:
        return

    st.header(
        f"📖 Редакция от {format_version(selected_version)}"
    )

    articles = law_data.get("articles", [])

    if not articles:
        st.warning("В выбранной редакции нет статей.")
        return

    search_query = st.text_input(
        "Поиск по номеру, заголовку или тексту статьи:",
        key="version_search",
        placeholder="Например: идентификация или 7",
    )

    filtered_articles = [
        article
        for article in articles
        if article_matches(article, search_query)
    ]

    filtered_articles.sort(key=article_sort_key)

    st.caption(
        f"Показано статей: {len(filtered_articles)} "
        f"из {len(articles)}"
    )

    if not filtered_articles:
        st.info("По вашему запросу статьи не найдены.")
        return

    for article in filtered_articles:
        article_number = article.get("article", "")
        title = article.get("title", "")
        full_text = article.get("full_article_text", "")
        points = article.get("points", [])

        with st.expander(
            f"Статья {article_number}: {title}",
            expanded=bool(search_query.strip()),
        ):
            if full_text:
                st.text(full_text)
            else:
                st.warning("Полный текст статьи отсутствует.")

            if points:
                st.divider()
                st.subheader("Пункты")

                for point in points:
                    if not isinstance(point, dict):
                        continue

                    point_number = point.get("p_num", "")
                    point_text = point.get("text", "")

                    st.markdown(
                        f"**Пункт {point_number}**"
                    )
                    st.write(point_text)


def render_comparison(versions):
    if len(versions) < 2:
        return

    st.sidebar.header("🔍 Сравнение редакций")

    ver1 = st.sidebar.selectbox(
        "Первая редакция:",
        versions,
        index=0,
        format_func=format_version,
        key="compare_version_1",
    )

    ver2 = st.sidebar.selectbox(
        "Вторая редакция:",
        versions,
        index=min(1, len(versions) - 1),
        format_func=format_version,
        key="compare_version_2",
    )

    if st.sidebar.button(
        "Сравнить редакции",
        key="compare_button",
    ):
        if ver1 == ver2:
            st.sidebar.warning(
                "Выберите две разные редакции."
            )
        else:
            try:
                data1 = load_version(ver1)
                data2 = load_version(ver2)

                st.session_state.compare_data = (
                    data1,
                    data2,
                    ver1,
                    ver2,
                )

            except Exception as exc:
                st.sidebar.error(
                    f"Ошибка сравнения: {exc}"
                )

    compare_data = st.session_state.get("compare_data")

    if not compare_data:
        return

    data1, data2, ver1, ver2 = compare_data

    st.header(
        "📊 Сравнение редакций "
        f"{format_version(ver1)} и {format_version(ver2)}"
    )

    articles1 = {
        str(article.get("article")): article
        for article in data1.get("articles", [])
    }

    articles2 = {
        str(article.get("article")): article
        for article in data2.get("articles", [])
    }

    all_article_numbers = (
        set(articles1.keys()) | set(articles2.keys())
    )

    def comparison_sort_key(article_number):
        try:
            return (0, float(article_number))
        except ValueError:
            return (1, article_number)

    added_count = 0
    removed_count = 0
    changed_count = 0
    unchanged_count = 0

    for article_number in sorted(
        all_article_numbers,
        key=comparison_sort_key,
    ):
        article1 = articles1.get(article_number)
        article2 = articles2.get(article_number)

        if article1 and article2:
            text1 = article1.get("full_article_text", "")
            text2 = article2.get("full_article_text", "")

            if text1 == text2:
                unchanged_count += 1
            else:
                changed_count += 1

        elif article1 and not article2:
            removed_count += 1

        elif article2 and not article1:
            added_count += 1

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Добавлено",
        added_count,
    )
    metric_columns[1].metric(
        "Удалено",
        removed_count,
    )
    metric_columns[2].metric(
        "Изменено",
        changed_count,
    )
    metric_columns[3].metric(
        "Без изменений",
        unchanged_count,
    )

    st.divider()

    for article_number in sorted(
        all_article_numbers,
        key=comparison_sort_key,
    ):
        article1 = articles1.get(article_number)
        article2 = articles2.get(article_number)

        if article1 and article2:
            text1 = article1.get("full_article_text", "")
            text2 = article2.get("full_article_text", "")

            if text1 == text2:
                st.success(
                    f"Статья {article_number}: без изменений"
                )
            else:
                st.warning(
                    f"Статья {article_number}: изменена"
                )

                with st.expander(
                    f"Показать текст статьи {article_number}"
                ):
                    st.markdown(
                        f"**Редакция {format_version(ver1)}**"
                    )
                    st.text(text1)

                    st.markdown(
                        f"**Редакция {format_version(ver2)}**"
                    )
                    st.text(text2)

        elif article1 and not article2:
            st.info(
                f"Статья {article_number}: "
                "удалена во второй редакции"
            )

            with st.expander(
                f"Показать удалённую статью {article_number}"
            ):
                st.text(
                    article1.get("full_article_text", "")
                )

        elif article2 and not article1:
            st.info(
                f"Статья {article_number}: "
                "добавлена во второй редакции"
            )

            with st.expander(
                f"Показать добавленную статью {article_number}"
            ):
                st.text(
                    article2.get("full_article_text", "")
                )


def render_document_analysis(model_choice):
    st.header("📄 Загрузка документа для анализа")

    uploaded_file = st.file_uploader(
        "Загрузите файл .docx",
        type=["docx"],
        key="document_uploader",
    )

    if not uploaded_file:
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    uploaded_path = RAW_DIR / uploaded_file.name

    with uploaded_path.open("wb") as file:
        file.write(uploaded_file.getbuffer())

    if st.button(
        "🚀 Обработать закон",
        key="process_document_button",
    ):
        with st.status(
            "Обработка документа...",
            expanded=True,
        ):
            try:
                st.write("1. Парсинг DOCX...")
                run_full_parse(uploaded_file.name)

                if model_choice == "Ollama (локально)":
                    st.write(
                        "2. Анализ через локальную Ollama..."
                    )
                    run_enrichment_ollama()

                else:
                    st.write(
                        "2. Анализ через DeepSeek/OpenRouter..."
                    )

                    api_key = st.session_state.get(
                        "openrouter_key",
                        "",
                    )

                    if not api_key:
                        st.error(
                            "Для DeepSeek требуется "
                            "API-ключ OpenRouter."
                        )
                        return

                    run_enrichment_openrouter(api_key)

                st.success("✅ Документ обработан.")

            except Exception as exc:
                st.error(
                    f"Ошибка обработки документа: {exc}"
                )
                return

        st.rerun()


def render_analysis_results(model_choice):
    smart_base_path = (
        PROCESSED_DIR / "smart_legal_base.json"
    )

    if not smart_base_path.exists():
        return

    try:
        with smart_base_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            database = json.load(file)

    except Exception as exc:
        st.error(
            f"Ошибка чтения результатов анализа: {exc}"
        )
        return

    st.header("📊 Результаты анализа")

    st.sidebar.info(
        "Последний анализ выполнен с помощью: "
        f"{model_choice}"
    )

    analysis_query = st.text_input(
        "Поиск по статьям в результатах анализа:",
        key="analysis_search",
        placeholder="Введите слово или номер статьи",
    )

    for article in database.get("articles", []):
        analysis = article.get("ai_analysis", {})

        if not isinstance(analysis, dict):
            analysis = {}

        article_text = str(
            article.get("full_article_text", "")
        ).lower()

        analysis_text = str(analysis).lower()

        article_number = str(
            article.get("article", "")
        ).lower()

        if analysis_query.strip():
            query = analysis_query.lower().strip()

            if (
                query not in article_text
                and query not in analysis_text
                and query not in article_number
            ):
                continue

        st.subheader(
            f"Статья {article.get('article', '')}: "
            f"{article.get('title', '')}"
        )

        column1, column2 = st.columns([1, 3])

        column1.metric(
            "РИСК",
            analysis.get("risk_level", "Не определён"),
        )

        column2.info(
            analysis.get(
                "short_summary",
                "Краткое описание отсутствует.",
            )
        )

        with st.expander("Детали анализа"):
            st.write(
                "🚫 Блокирующая: "
                f"{analysis.get('is_blocking_norm', 'Не определено')}"
            )
            st.write(
                "🎯 Требование: "
                f"{analysis.get('main_requirement', '')}"
            )
            st.write(
                "⚖️ Санкции: "
                f"{analysis.get('sanctions', '')}"
            )

            st.divider()
            st.text(
                article.get(
                    "full_article_text",
                    "",
                )
            )


def main():
    initialize_session_state()

    render_model_settings()

    versions, selected_version, law_data = (
        render_version_sidebar()
    )

    render_comparison(versions)

    render_version_view(
        selected_version,
        law_data,
    )

    render_document_analysis(
        st.session_state.model_choice
    )

    render_analysis_results(
        st.session_state.model_choice
    )


if __name__ == "__main__":
    main()