import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "http://pravo.gov.ru/proxy/ips/?docbody=&nd=102072376"

def fetch_version(date_str=None):
    url = BASE_URL
    if date_str:
        url += f"&rd={date_str}"
    response = requests.get(url)
    # Принудительно устанавливаем кодировку windows-1251
    response.encoding = 'windows-1251'
    return response.text

def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Ищем контейнер с текстом документа
    content_div = None
    # Вариант 1: по классу docbody_text
    content_div = soup.find('div', class_='docbody_text')
    if not content_div:
        content_div = soup.find('div', class_='document-body')
    if not content_div:
        content_div = soup.find('div', class_='content')
    if not content_div:
        content_div = soup.find('div', class_='text')
    if not content_div:
        # Вариант 2: ищем любой div, содержащий слово "Статья"
        for div in soup.find_all('div'):
            text = div.get_text(strip=True)
            if 'Статья' in text:
                content_div = div
                break
    if not content_div:
        # Если ничего не нашли – берём всё body
        content_div = soup.body

    # Извлекаем текст из параграфов
    lines = []
    for element in content_div.find_all(['p', 'div', 'span']):
        text = element.get_text(strip=True)
        if text:
            lines.append(text)

    full_text = '\n'.join(lines)

    # Если текст слишком короткий – берём весь текст из body
    if len(full_text) < 100:
        full_text = soup.body.get_text(separator='\n', strip=True)

    # Разбиваем на статьи
    article_pattern = re.compile(r'(?m)^Статья\s+(\d+(?:\.\d+)*)\.?\s*(.*)')
    parts = re.split(article_pattern, full_text)
    
    articles = []
    for i in range(1, len(parts), 3):
        art_num = parts[i].strip()
        art_title = parts[i+1].strip() if i+1 < len(parts) else ""
        art_content = parts[i+2].strip() if i+2 < len(parts) else ""
        art_content = re.sub(r'(?m)(?:Глава|Раздел)\s+[IVXLCDM]+\..*$', '', art_content).strip()

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

def save_version(data, date_str):
    os.makedirs("data/versions", exist_ok=True)
    filename = f"data/versions/{date_str}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return filename

def load_version(date_str):
    filename = f"data/versions/{date_str}.json"
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_current_date_str():
    return datetime.now().strftime("%Y%m%d")

def download_and_save_latest():
    date_str = get_current_date_str()
    html = fetch_version()
    data = parse_html(html)
    return save_version(data, date_str)