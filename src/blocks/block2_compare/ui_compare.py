"""
UI таба 2: сравнение версий закона.
"""
import json
from pathlib import Path

import streamlit as st

from .comparator import (
    get_available_versions,
    format_version,
    load_version,
    article_matches,
    article_sort_key,
    compare_versions,
)


def render_version_view(selected_version, law_data):
    """Просмотр выбранной редакции."""
    if not selected_version or not law_data:
        return

    st.header(f"📖 Редакция от {format_version(selected_version)}")

    articles = law_data.get("articles", [])
    if not articles:
        st.warning("В выбранной редакции нет статей.")
        return

    search_query = st.text_input(
        "Поиск по номеру, заголовку или тексту статьи:",
        key="version_search",
        placeholder="Например: идентификация или 7",
    )

    filtered = [
        a for a in articles if article_matches(a, search_query)
    ]
    filtered.sort(key=article_sort_key)

    st.caption(f"Показано статей: {len(filtered)} из {len(articles)}")

    for article in filtered:
        number = article.get("article", "")
        title = article.get("title", "")
        full_text = article.get("full_article_text", "")
        points = article.get("points", [])

        with st.expander(
            f"Статья {number}: {title}",
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
                    st.markdown(f"**Пункт {point.get('p_num', '')}**")
                    st.write(point.get("text", ""))


def render_comparison(versions):
    """Сравнение двух редакций."""
    if len(versions) < 2:
        st.info("Для сравнения нужно минимум две редакции.")
        return

    col1, col2 = st.columns(2)

    with col1:
        ver1 = st.selectbox(
            "Первая редакция:",
            versions,
            index=0,
            format_func=format_version,
            key="compare_version_1",
        )
    with col2:
        ver2 = st.selectbox(
            "Вторая редакция:",
            versions,
            index=min(1, len(versions) - 1),
            format_func=format_version,
            key="compare_version_2",
        )

    if not st.button("Сравнить редакции", key="compare_button"):
        return

    if ver1 == ver2:
        st.warning("Выберите две разные редакции.")
        return

    try:
        data1 = load_version(ver1)
        data2 = load_version(ver2)
    except Exception as exc:
        st.error(f"Ошибка загрузки: {exc}")
        return

    st.header(
        f"📊 Сравнение редакций "
        f"{format_version(ver1)} и {format_version(ver2)}"
    )

    diff = compare_versions(data1, data2)
    counts = diff["counts"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Добавлено", counts["added"])
    m2.metric("Удалено", counts["removed"])
    m3.metric("Изменено", counts["changed"])
    m4.metric("Без изменений", counts["unchanged"])

    st.divider()

    for item in diff["articles"]:
        number = item["article"]
        status = item["status"]

        if status == "unchanged":
            st.success(f"Статья {number}: без изменений")

        elif status == "changed":
            st.warning(f"Статья {number}: изменена")
            with st.expander(f"Показать текст статьи {number}"):
                st.markdown(f"**Редакция {format_version(ver1)}**")
                st.text(item["old"].get("full_article_text", ""))
                st.markdown(f"**Редакция {format_version(ver2)}**")
                st.text(item["new"].get("full_article_text", ""))

        elif status == "removed":
            st.info(f"Статья {number}: удалена во второй редакции")
            with st.expander(f"Показать удалённую статью {number}"):
                st.text(item["old"].get("full_article_text", ""))

        elif status == "added":
            st.info(f"Статья {number}: добавлена во второй редакции")
            with st.expander(f"Показать добавленную статью {number}"):
                st.text(item["new"].get("full_article_text", ""))


def render():
    """Главная точка входа для таба 2."""
    st.subheader("📊 Сравнение версий закона")
    st.caption("Выберите две редакции и нажмите «Сравнить»")

    versions = get_available_versions()

    if not versions:
        st.warning(
            "Нет сохранённых редакций. "
            "Файлы должны лежать в data/115-fz/versions/ "
            "в формате YYYYMMDD.json."
        )
        return

    tab_view, tab_compare = st.tabs(["📖 Просмотр", "🔍 Сравнение"])

    with tab_view:
        selected = st.selectbox(
            "Выберите редакцию:",
            versions,
            format_func=format_version,
            key="selected_version_tab",
        )
        try:
            data = load_version(selected)
            render_version_view(selected, data)
        except Exception as exc:
            st.error(f"Ошибка чтения редакции: {exc}")

    with tab_compare:
        render_comparison(versions)
