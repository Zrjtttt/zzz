"""
Сравнение версий закона.
Чистая логика — без Streamlit.
"""
import json
from datetime import datetime
from pathlib import Path


VERSIONS_DIR = Path("data/115-fz/versions")


def get_available_versions():
    """Возвращает список редакций в формате YYYYMMDD."""
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

    versions = []
    for path in VERSIONS_DIR.glob("*.json"):
        date_str = path.stem
        if date_str == "sample":
            continue
        try:
            datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            continue
        versions.append(date_str)

    return sorted(set(versions), reverse=True)


def format_version(version):
    """YYYYMMDD -> YYYY-MM-DD."""
    if len(version) == 8 and version.isdigit():
        return f"{version[:4]}-{version[4:6]}-{version[6:8]}"
    return version


def load_version(version):
    """Загружает JSON выбранной редакции."""
    version_path = VERSIONS_DIR / f"{version}.json"

    if not version_path.exists():
        raise FileNotFoundError(f"Файл редакции не найден: {version_path}")

    with version_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Файл редакции должен содержать JSON-объект.")

    if not isinstance(data.get("articles"), list):
        raise ValueError("В файле редакции отсутствует массив 'articles'.")

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


def _comparison_sort_key(article_number):
    try:
        return (0, float(article_number))
    except ValueError:
        return (1, article_number)


def compare_versions(data1, data2):
    """
    Сравнивает две версии закона.
    Возвращает структуру с diff по каждой статье.
    """
    articles1 = {
        str(a.get("article")): a for a in data1.get("articles", [])
    }
    articles2 = {
        str(a.get("article")): a for a in data2.get("articles", [])
    }

    all_numbers = set(articles1.keys()) | set(articles2.keys())

    result = {
        "articles": [],
        "counts": {
            "added": 0,
            "removed": 0,
            "changed": 0,
            "unchanged": 0,
        },
    }

    for number in sorted(all_numbers, key=_comparison_sort_key):
        a1 = articles1.get(number)
        a2 = articles2.get(number)

        if a1 and a2:
            text1 = a1.get("full_article_text", "")
            text2 = a2.get("full_article_text", "")
            if text1 == text2:
                status = "unchanged"
            else:
                status = "changed"
            result["articles"].append({
                "article": number,
                "status": status,
                "old": a1,
                "new": a2,
            })
        elif a1 and not a2:
            status = "removed"
            result["articles"].append({
                "article": number,
                "status": status,
                "old": a1,
                "new": None,
            })
        elif a2 and not a1:
            status = "added"
            result["articles"].append({
                "article": number,
                "status": status,
                "old": None,
                "new": a2,
            })

        result["counts"][status] += 1

    return result
