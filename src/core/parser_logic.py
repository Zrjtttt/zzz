import docx
import re
import json
import os

def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([para.text.strip() for para in doc.paragraphs if para.text.strip()])

def parse_legal_text(text):
    text = re.sub(r'(?m)^(?:Глава|Раздел)\s+[IVXLCDM]+\..*$', '', text)
    article_pattern = r'(?m)^Статья\s+(\d+(?:\.\d+)*)\.?\s*(.*)'
    parts = re.split(article_pattern, text)
    law_structure = {"articles": []}

    for i in range(1, len(parts), 3):
        art_num = parts[i]
        art_title = parts[i+1].strip()
        art_content = parts[i+2].strip() if i+2 < len(parts) else ""
        art_content = re.sub(r'(?m)(?:Глава|Раздел)\s+[IVXLCDM]+\..*$', '', art_content).strip()

        paragraphs = []
        if art_num == "3": # Логика для определений
            raw_defs = art_content.split('\n')
            for idx, line in enumerate(raw_defs):
                if " - " in line:
                    paragraphs.append({"p_num": str(idx+1), "text": line.strip()})
        else: # Обычные пункты
            p_parts = re.split(r'(?m)^\s*(\d+)\s*[\.\)]\s+', art_content)
            if len(p_parts) > 1:
                for j in range(1, len(p_parts), 2):
                    paragraphs.append({"p_num": p_parts[j], "text": p_parts[j+1].strip()})
            else:
                paragraphs.append({"p_num": "1", "text": art_content})

        law_structure["articles"].append({
            "article": art_num,
            "title": art_title,
            "full_article_text": art_content,
            "points": paragraphs
        })
    return law_structure

def run_full_parse(input_filename):
    input_path = f"data/raw/{input_filename}"
    output_path = "data/processed/legal_knowledge_base.json"
    text = extract_text_from_docx(input_path)
    data = parse_legal_text(text)
    os.makedirs("data/processed", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return output_path