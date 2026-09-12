import requests
import os
import json
import re
from email.parser import BytesParser
from email import policy
from email.message import EmailMessage
import quopri
from bs4 import BeautifulSoup
from bs4 import NavigableString

# Ссылка на файл (MIME-архив)
ARCHIVE_URL = "http://pravo.gov.ru/proxy/ips/?savertf=&nd=102072376&page=all"

def download_archive(save_path="data/raw/115-fz.mht"):
    """Скачивает MIME-архив с pravo.gov.ru"""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    response = requests.get(ARCHIVE_URL)
    response.raise_for_status()
    with open(save_path, 'wb') as f:
        f.write(response.content)
    return save_path

def parse_mht_to_text(mht_path):
    """
    Извлекает чистый текст из MIME-архива (multipart/related) с HTML-частью.
    """
    with open(mht_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)

    html_payload = None
    # Ищем часть с типом text/html
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == 'text/html':
            # Получаем содержимое, декодируем quoted-printable, если нужно
            payload = part.get_payload(decode=True)  # автоматически декодирует quoted-printable и base64
            if payload:
                # Пробуем декодировать из windows-1251 в utf-8
                try:
                    html_payload = payload.decode('windows-1251')
                except UnicodeDecodeError:
                    try:
                        html_payload = payload.decode('utf-8')
                    except:
                        html_payload = payload.decode('utf-8', errors='ignore')
                break

    if not html_payload:
        raise ValueError("Не найдена HTML-часть в архиве")

    # Используем BeautifulSoup для извлечения текста
    soup = BeautifulSoup(html_payload, 'html.parser')
    # Удаляем скрипты и стили
    for script in soup(["script", "style"]):
        script.decompose()

    # Получаем текст
    text = soup.get_text(separator='\n', strip=True)
    return text


class LawStructureError(ValueError):
    """Raised when the MHT does not contain a trustworthy article structure."""

    status = "review_required"


ARTICLE_HEADING_PATTERN = re.compile(
    r"^Статья\s+(\d+)(?:\s+(\d+))?(?:\s*-\s*(\d+))?\s*\.\s*(.*)$"
)
ARTICLE_NUMBER_PATTERN = re.compile(
    r"^\d+(?:\.\d+)?(?:-\d+)?$"
)


def _decode_mht_html(mht_path):
    with open(mht_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)

    for part in msg.walk():
        if part.get_content_type() != 'text/html':
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            break

        for encoding in ('windows-1251', 'utf-8'):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue

        return payload.decode('utf-8', errors='ignore')

    raise ValueError("Не найдена HTML-часть в архиве")


def _normalise_article_heading(text):
    value = ' '.join(text.split())
    match = ARTICLE_HEADING_PATTERN.fullmatch(value)
    if not match:
        return None

    major, minor, suffix, title = match.groups()
    article_number = major
    if minor:
        article_number += f".{minor}"
    if suffix:
        article_number += f"-{suffix}"

    return article_number, title.strip()


def _article_order_key(article_number):
    match = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:-(\d+))?", article_number)
    if not match:
        return None

    major, minor, suffix = match.groups()
    return (
        int(major),
        int(minor or 0),
        int(suffix) if suffix is not None else -1,
    )


def _text_between(headings, index):
    heading = headings[index]
    next_heading = headings[index + 1] if index + 1 < len(headings) else None
    chunks = []

    for sibling in heading.next_siblings:
        if sibling is next_heading:
            break
        if isinstance(sibling, NavigableString):
            text = str(sibling).strip()
        else:
            text = sibling.get_text(separator='\n', strip=True)
        if text:
            chunks.append(text)

    return '\n'.join(chunks).strip()


def parse_mht_law(mht_path):
    """Parse article boundaries from structural MHT HTML headings."""
    soup = BeautifulSoup(_decode_mht_html(mht_path), 'html.parser')
    body = soup.body
    if body is None:
        raise LawStructureError("В HTML MHT отсутствует body")

    headings = [
        node for node in body.find_all('p', class_='H', recursive=False)
        if node.parent is body
    ]
    if not headings:
        raise LawStructureError("Не найдены структурные заголовки p.H")

    articles = []
    suspicious_headings = []
    article_headings = []
    for heading in headings:
        heading_text = ' '.join(heading.get_text(' ', strip=True).split())
        if not heading_text.startswith('Статья'):
            continue

        article_headings.append(heading)
        parsed_heading = _normalise_article_heading(heading_text)
        if parsed_heading is None:
            suspicious_headings.append(heading_text)
            continue

        article_number, title = parsed_heading
        articles.append({
            "article": article_number,
            "title": title,
            "full_article_text": "",
            "points": [],
        })

    numbers = [article["article"] for article in articles]
    duplicates = sorted({number for number in numbers if numbers.count(number) > 1})
    invalid_numbers = [number for number in numbers if not ARTICLE_NUMBER_PATTERN.fullmatch(number)]
    order_keys = [_article_order_key(number) for number in numbers]
    order_errors = [
        (numbers[index - 1], numbers[index])
        for index in range(1, len(numbers))
        if order_keys[index] <= order_keys[index - 1]
    ]

    if (
        not articles
        or duplicates
        or any(not number for number in numbers)
        or invalid_numbers
        or suspicious_headings
        or order_errors
    ):
        problems = []
        if not articles:
            problems.append("статьи не найдены")
        if duplicates:
            problems.append(f"дубли номеров: {duplicates}")
        if invalid_numbers:
            problems.append(f"недопустимые номера: {invalid_numbers}")
        if suspicious_headings:
            problems.append(f"подозрительные заголовки: {suspicious_headings}")
        if order_errors:
            problems.append(f"нарушение порядка: {order_errors}")
        raise LawStructureError("; ".join(problems))

    for index, article in enumerate(articles):
        article["full_article_text"] = _text_between(article_headings, index)
        text = article["full_article_text"]
        point_parts = re.split(r'(?m)^\s*(\d+)\s*[\.\)]\s+', text)
        if len(point_parts) > 1:
            for point_index in range(1, len(point_parts), 2):
                article["points"].append({
                    "p_num": point_parts[point_index],
                    "text": point_parts[point_index + 1].strip(),
                })
        else:
            article["points"].append({"p_num": "1", "text": text})

    return {"articles": articles}

def parse_law_text(text):
    """Разбивает текст закона на статьи (адаптация parser_logic.py)"""
    # Очищаем от лишних заголовков
    text = re.sub(r'(?m)^(ФЕДЕРАЛЬНЫЙ ЗАКОН|Принят|Одобрен|Введен|Настоящий Федеральный закон).*$', '', text)

    # Паттерн для статей
    article_pattern = re.compile(r'(?m)^Статья\s+(\d+(?:\.\d+)*)\.?\s*(.*)')
    parts = re.split(article_pattern, text)

    articles = []
    for i in range(1, len(parts), 3):
        art_num = parts[i].strip()
        art_title = parts[i+1].strip() if i+1 < len(parts) else ""
        art_content = parts[i+2].strip() if i+2 < len(parts) else ""

        # Убираем заголовки глав внутри текста
        art_content = re.sub(r'(?m)(?:Глава|Раздел)\s+[IVXLCDM]+\..*$', '', art_content).strip()

        # Разбиваем на пункты
        points = []
        p_parts = re.split(r'(?m)^\s*(\d+)\s*[\.\)]\s+', art_content)
        if len(p_parts) > 1:
            for j in range(1, len(p_parts), 2):
                points.append({
                    "p_num": p_parts[j],
                    "text": p_parts[j+1].strip() if j+1 < len(p_parts) else ""
                })
        else:
            points.append({"p_num": "1", "text": art_content})

        articles.append({
            "article": art_num,
            "title": art_title,
            "full_article_text": art_content,
            "points": points
        })

    return {"articles": articles}

def fetch_and_parse_law(editorial_date="20260610"):
    """
    Основная функция: скачивает MIME-архив, извлекает HTML, парсит, сохраняет JSON.
    """
    # 1. Скачиваем архив
    archive_path = download_archive()
    print(f"Архив сохранён: {archive_path}")

    # 2. Извлекаем текст из архива
    # 3. Парсим текст закона
    law_data = parse_mht_law(archive_path)
    print(f"Найдено статей: {len(law_data['articles'])}")

    # 4. Сохраняем JSON
    os.makedirs("data/versions", exist_ok=True)
    json_path = f"data/versions/{editorial_date}_corrected.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(law_data, f, ensure_ascii=False, indent=4)
    print(f"Сохранено: {json_path}")

    return json_path

if __name__ == "__main__":
    fetch_and_parse_law()