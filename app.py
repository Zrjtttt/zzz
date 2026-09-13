#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LEGAL QA SYSTEM - Интерфейс с двумя табами
Таб 1: проверка документа (чек-лист + AI-анализ)
Таб 2: сравнение версий закона
"""

import streamlit as st
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.search.bm25 import BM25Search
from src.understanding.question_frame import QuestionFrame
from src.router.router import Router
from src.check_verifier import CheckVerifier


# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================

@st.cache_resource
def load_system():
    data_dir = Path(__file__).parent / 'data' / '115-fz' / 'processed'
    norms_file = data_dir / 'norms.json'
    graph_file = data_dir / 'graph.json'
    checks_file = data_dir / 'checks.json'

    with open(norms_file, 'r', encoding='utf-8') as f:
        norms_data = json.load(f)

    norms = norms_data.get('norms', {})
    norm_ids = list(norms.keys())
    norm_texts = [norms[nid]['original_text'] for nid in norm_ids]

    graph = None
    if graph_file.exists():
        with open(graph_file, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        graph = graph_data.get('graph', {})

    bm25 = BM25Search(norm_ids, norm_texts)
    bm25.build_index()

    qf = QuestionFrame()
    router = Router(norm_ids, norm_texts, norms, bm25, qf, graph)

    verifier = None
    if checks_file.exists():
        verifier = CheckVerifier(str(checks_file))

    return router, norms, verifier


# ============================================================
# ВОПРОСЫ ДЛЯ ЛЕВОЙ КОЛОНКИ (НЕ МЕНЯЕМ)
# ============================================================

QUESTIONS_LEFT = [
    {"id": "q1", "category": "КТО?", "text": "Кто является бенефициарным владельцем?", "norm_id": "8",
     "expected": "Физическое лицо, владеющее более 25% капитала или контролирующее действия"},
    {"id": "q2", "category": "КТО?", "text": "Кто обязан раскрывать информацию?", "norm_id": "1",
     "expected": "Юридическое лицо"},
    {"id": "q3", "category": "ЧТО ДЕЛАТЬ?", "text": "Как часто нужно обновлять информацию?", "norm_id": "3.1",
     "expected": "Не реже одного раза в год, а также при изменении сведений"},
    {"id": "q4", "category": "ЧТО ДЕЛАТЬ?", "text": "Сколько лет нужно хранить информацию?", "norm_id": "3.2",
     "expected": "Не менее пяти лет"},
    {"id": "q5", "category": "КОМУ?", "text": "Перед какими органами нужно отчитываться?", "norm_id": "6",
     "expected": "Уполномоченный орган, налоговые органы, федеральный орган по регистрации НКО"},
]


# ============================================================
# ВОПРОСЫ ДЛЯ ПРАВОЙ КОЛОНКИ (ПРОВЕРКА ДОКУМЕНТА)
# ============================================================

QUESTIONS_RIGHT = [
    {"id": "d1", "text": "Кто является бенефициарным владельцем?", "norm_id": "8",
     "expected": "Физическое лицо, владеющее более 25% капитала или контролирующее действия"},
    {"id": "d2", "text": "Кто обязан раскрывать информацию?", "norm_id": "1",
     "expected": "Юридическое лицо"},
    {"id": "d3", "text": "Как часто нужно обновлять информацию?", "norm_id": "3.1",
     "expected": "Не реже одного раза в год, а также при изменении сведений"},
    {"id": "d4", "text": "Сколько лет нужно хранить информацию?", "norm_id": "3.2",
     "expected": "Не менее пяти лет"},
    {"id": "d5", "text": "Перед какими органами нужно отчитываться?", "norm_id": "6",
     "expected": "Уполномоченный орган, налоговые органы, федеральный орган по регистрации НКО"},
]


# ============================================================
# ИЗВЛЕЧЕНИЕ ТЕКСТА ИЗ ЗАГРУЖЕННОГО ФАЙЛА
# ============================================================

def extract_text_from_file(uploaded_file) -> str:
    """
    Извлекает текст из загруженного файла.
    Поддерживает: TXT, DOCX, PDF.
    """
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()

    if name.endswith('.txt'):
        return raw.decode('utf-8', errors='ignore')

    if name.endswith('.docx'):
        import io
        import docx
        doc = docx.Document(io.BytesIO(raw))
        return "\n".join(
            p.text for p in doc.paragraphs if p.text.strip()
        )

    if name.endswith('.pdf'):
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return "\n".join(pages)

    raise ValueError(f"Неподдерживаемый формат файла: {uploaded_file.name}")


# ============================================================
# ФУНКЦИЯ: AI-АНАЛИЗ ДОКУМЕНТА (СТРУКТУРИРОВАННЫЙ JSON)
# ============================================================

def call_ai_analysis(api_key: str, question: str, expected: str, document_text: str,
                     requirements: list) -> dict:
    """
    Отправляет вопрос + эталон + документ + требования в ИИ.
    ИИ возвращает структурированный JSON с фактами.
    """
    import requests

    req_list = "\n".join([f"{r['id']}: {r['text']}" for r in requirements])

    prompt = f"""Ты — система проверки документов по статье 6.1 115-ФЗ.

Пользователь проверяет документ по вопросу:
"{question}"

Что требует закон:
"{expected}"

Требования (R1-R4):
{req_list}

Документ:
{document_text[:15000]}

ЗАДАЧА:
1. Найди в документе ответ на вопрос
2. Для каждого требования (R1-R4) извлеки факты:
   - action: "update" / "document" / null
   - object: "beneficiary_information" / "received_information" / null
   - frequency: число (месяцев) / null
   - condition: "on_change" / null
3. Укажи фрагмент документа, где это найдено (цитата)
4. Оцени статус каждого требования: ВЫПОЛНЕНО / ЧАСТИЧНО / НЕ ВЫПОЛНЕНО / НЕЯСНО
5. Сделай общий вывод

Верни ТОЛЬКО JSON. БЕЗ пояснений.

ФОРМАТ JSON:
{{
  "question": "{question}",
  "document_facts": {{
    "R1": {{
      "action": "update",
      "object": "beneficiary_information",
      "fragment": "цитата из документа",
      "status": "ВЫПОЛНЕНО"
    }},
    "R2": {{
      "frequency": 12,
      "fragment": "цитата",
      "status": "ВЫПОЛНЕНО"
    }},
    "R3": {{
      "condition": null,
      "fragment": null,
      "status": "НЕ ВЫПОЛНЕНО"
    }},
    "R4": {{
      "action": "document",
      "object": "beneficiary_information",
      "fragment": "цитата",
      "status": "ВЫПОЛНЕНО"
    }}
  }},
  "verdict": "COMPLIANT / PARTIAL / NOT_FOUND / UNCLEAR",
  "explanation": "краткое объяснение результата"
}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "Legal QA System"
    }

    payload = {
        "model": "deepseek/deepseek-chat-v3-0324",
        "messages": [
            {"role": "system", "content": "Ты — система извлечения фактов. Отвечай только JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2500
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=120
        )
        if response.status_code != 200:
            return {"error": f"Ошибка API: {response.status_code}"}

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            return {"error": "Не удалось извлечь JSON", "raw": content[:500]}
    except Exception as e:
        return {"error": str(e)}


def check_api_key(api_key: str) -> bool:
    """Проверяет, работает ли API-ключ"""
    import requests
    if not api_key:
        return False
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek/deepseek-chat-v3-0324",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 5
            },
            timeout=15
        )
        return response.status_code == 200
    except Exception:
        return False


def get_requirements_for_question(norm_id: str) -> list:
    """Возвращает требования (R1-R4) для конкретной нормы."""
    if norm_id == "3.1":
        return [
            {"id": "R1", "text": "Обновлять информацию о бенефициарных владельцах"},
            {"id": "R2", "text": "Не реже одного раза в год"},
            {"id": "R3", "text": "При изменении сведений"},
            {"id": "R4", "text": "Документально фиксировать полученную информацию"},
        ]
    else:
        return [
            {"id": "R1", "text": "Соответствие требованию"},
        ]


# ============================================================
# ТАБ 1: ПРОВЕРКА ДОКУМЕНТА
# ============================================================

def render_block1():
    # ============================================================
    # БОКОВАЯ ПАНЕЛЬ: API-КЛЮЧ
    # ============================================================

    with st.sidebar:
        st.header("🔑 API-ключ OpenRouter")

        api_key_input = st.text_input(
            "Введите ключ для AI-анализа:",
            type="password",
            key="api_key_input",
            help="Ключ нужен для AI-анализа документа."
        )

        if api_key_input:
            if st.session_state.get('api_key_checked') != api_key_input:
                with st.spinner("Проверка ключа..."):
                    is_valid = check_api_key(api_key_input)
                st.session_state['api_key_valid'] = is_valid
                st.session_state['api_key_checked'] = api_key_input

            if st.session_state.get('api_key_valid'):
                st.success("✅ Ключ работает — AI доступен")
            else:
                st.error("❌ Ключ не работает")
        else:
            st.info("ℹ️ Без ключа AI-анализ недоступен")

        st.divider()
        st.caption("Левая колонка: ответы из закона")
        st.caption("Правая колонка: проверка документа")

    api_key = st.session_state.get('api_key_checked', '') if st.session_state.get('api_key_valid') else ''

    # Загружаем систему
    with st.spinner("Загрузка..."):
        router, norms, verifier = load_system()

    # ДВЕ КОЛОНКИ
    col_left, col_right = st.columns(2, gap="large")

    # ============================================================
    # ЛЕВАЯ КОЛОНКА: ЧЕК-ЛИСТ
    # ============================================================

    with col_left:
        st.subheader("📋 Что требует закон")
        st.caption("Нажмите на вопрос — получите ответ из закона")

        current_category = None
        for q in QUESTIONS_LEFT:
            if q['category'] != current_category:
                current_category = q['category']
                st.markdown(f"**{current_category}**")

            if st.button(
                f"☑️ {q['text']}",
                key=f"manual_{q['id']}",
                use_container_width=True,
                type="secondary"
            ):
                st.session_state['selected_question'] = q['id']
                st.rerun()

        st.divider()

        if 'selected_question' in st.session_state:
            q_id = st.session_state['selected_question']
            q = next((q for q in QUESTIONS_LEFT if q['id'] == q_id), None)

            if q:
                st.markdown("### 📖 Ответ из закона")
                st.success(q['expected'])
                st.markdown(f"**📌 Источник:** Норма {q['norm_id']}")

                norm_text = norms.get(q['norm_id'], {}).get('original_text', '')
                if norm_text:
                    with st.expander("📖 Показать полный текст нормы"):
                        st.text(norm_text)

        st.divider()
        st.caption("💡 Выберите вопрос слева — узнайте, что требует закон")

    # ============================================================
    # ПРАВАЯ КОЛОНКА: ПРОВЕРКА ДОКУМЕНТА
    # ============================================================

    with col_right:
        st.subheader("📄 Проверка документа")
        st.caption(
            "Загрузите документ, выберите вопрос — "
            "и он уйдёт в AI-анализ"
        )

        # Загрузка документа
        uploaded_file = st.file_uploader(
            "Загрузите документ (TXT, DOCX, PDF)",
            type=['txt', 'docx', 'pdf'],
            key="document_uploader_right"
        )

        if uploaded_file is not None:
            try:
                document_text = extract_text_from_file(uploaded_file)
                st.success(
                    f"✅ Загружен: {uploaded_file.name} "
                    f"({len(document_text)} символов)"
                )
            except Exception as exc:
                st.error(f"❌ Ошибка чтения файла: {exc}")
                document_text = None

            if document_text:
                st.divider()
                st.markdown("**Выберите вопрос для анализа:**")
                st.caption(
                    "AI-анализ запустится автоматически "
                    "после выбора вопроса"
                )

                question_options = {
                    q['id']: q['text'] for q in QUESTIONS_RIGHT
                }

                selected_q_id = st.selectbox(
                    "Вопрос",
                    options=list(question_options.keys()),
                    format_func=lambda x: question_options[x],
                    index=None,
                    placeholder="— выберите вопрос —",
                    key="question_selector"
                )

                selected_q = next(
                    (q for q in QUESTIONS_RIGHT if q['id'] == selected_q_id),
                    None
                )

                # === AI-АНАЛИЗ: только после явного выбора вопроса ===
                if selected_q is None:
                    st.info(
                        "ℹ️ Выберите вопрос из списка — "
                        "документ уйдёт в AI-анализ"
                    )

                elif not api_key:
                    st.warning(
                        "⚠️ Введите API-ключ в боковой панели, "
                        "чтобы запустить AI-анализ"
                    )

                else:
                    cache_key = f"{selected_q_id}_{len(document_text)}"
                    if st.session_state.get('ai_cache_key') != cache_key:
                        # Сбрасываем предыдущий результат
                        st.session_state.pop('ai_result', None)

                        with st.status(
                            "⏳ AI анализирует документ...",
                            expanded=True
                        ) as status:
                            st.write(f"Вопрос: {selected_q['text']}")
                            st.write("Отправка в DeepSeek...")

                            requirements = get_requirements_for_question(
                                selected_q['norm_id']
                            )
                            ai_result = call_ai_analysis(
                                api_key,
                                selected_q['text'],
                                selected_q['expected'],
                                document_text,
                                requirements
                            )

                            st.session_state['ai_result'] = ai_result
                            st.session_state['ai_cache_key'] = cache_key
                            status.update(
                                label="✅ AI-анализ готов",
                                state="complete"
                            )

                # === КНОПКА "ПРОВЕРИТЬ" (БЕЗ ИИ) ===
                if st.button("🔍 Проверить документ (без ИИ)", type="primary", use_container_width=True):
                    if selected_q is None:
                        st.error("Сначала выберите вопрос")
                    else:
                        st.divider()
                        st.subheader("📊 Результат проверки (логика без ИИ)")

                        st.markdown(f"**Вопрос:** {selected_q['text']}")

                        st.markdown("---")
                        st.markdown("**📖 Что требует закон:**")
                        st.success(selected_q['expected'])
                        st.caption(f"📌 Источник: норма {selected_q['norm_id']}")

                        st.markdown("---")
                        st.markdown("**📄 Что найдено в документе:**")

                        temp_path = Path("/tmp/uploaded_doc_check.txt")
                        temp_path.write_text(document_text, encoding='utf-8')

                        if verifier:
                            result = verifier.verify(str(temp_path))

                            for req_id, req_result in result['requirements'].items():
                                status = req_result['result']
                                if status == 'COMPLIANT':
                                    icon, status_text = "✅", "ВЫПОЛНЕНО"
                                elif status == 'PARTIAL':
                                    icon, status_text = "⚠️", "ЧАСТИЧНО"
                                elif status == 'NOT_FOUND':
                                    icon, status_text = "❌", "НЕ ВЫПОЛНЕНО"
                                else:
                                    icon, status_text = "❓", "НЕЯСНО"

                                st.markdown(f"{icon} **{req_id}:** {req_result['description']} — **{status_text}**")

                                facts = req_result.get('facts', {})
                                if facts:
                                    found_items = [f"{k}: {v}" for k, v in facts.items() if v is not None]
                                    if found_items:
                                        st.caption(f"   📄 Найдено: {', '.join(found_items)}")

                            verdict = result['verdict']
                            st.divider()

                            if verdict == 'COMPLIANT':
                                st.success("✅ ВЕРДИКТ: Документ ПОЛНОСТЬЮ соответствует")
                            elif verdict == 'PARTIAL':
                                st.warning("⚠️ ВЕРДИКТ: Документ соответствует ЧАСТИЧНО")
                            elif verdict == 'NOT_FOUND':
                                st.error("❌ ВЕРДИКТ: Требования НЕ ВЫПОЛНЕНЫ")
                            else:
                                st.info("❓ ВЕРДИКТ: НЕ УДАЛОСЬ ОДНОЗНАЧНО ОПРЕДЕЛИТЬ")
                        else:
                            st.warning("⚠️ Verifier не загружен")

                        temp_path.unlink(missing_ok=True)

                # === AI-АНАЛИЗ СНИЗУ ===
                current_cache_key = None
                if selected_q is not None:
                    current_cache_key = f"{selected_q_id}_{len(document_text)}"

                if (
                    st.session_state.get('ai_result')
                    and st.session_state.get('ai_cache_key') == current_cache_key
                ):
                    ai_result = st.session_state['ai_result']

                    st.divider()
                    st.subheader("🤖 AI-анализ документа")

                    if 'error' in ai_result:
                        st.error(f"Ошибка AI: {ai_result['error']}")
                    else:
                        st.markdown("**Что AI нашёл в документе:**")

                        facts_data = ai_result.get('document_facts', {})
                        for req_id, req_data in facts_data.items():
                            status = req_data.get('status', 'НЕЯСНО')
                            if status == 'ВЫПОЛНЕНО':
                                icon = "✅"
                            elif status == 'ЧАСТИЧНО':
                                icon = "⚠️"
                            elif status == 'НЕ ВЫПОЛНЕНО':
                                icon = "❌"
                            else:
                                icon = "❓"

                            st.markdown(f"{icon} **{req_id}:** {status}")

                            fragment = req_data.get('fragment')
                            if fragment:
                                st.caption(f"   📄 Фрагмент: \"{fragment[:200]}\"")

                            facts = {k: v for k, v in req_data.items()
                                     if k not in ['fragment', 'status'] and v is not None}
                            if facts:
                                st.caption(f"   🔍 Факты: {facts}")

                        ai_verdict = ai_result.get('verdict', 'UNCLEAR')
                        explanation = ai_result.get('explanation', '')

                        st.divider()
                        if ai_verdict == 'COMPLIANT':
                            st.success(f"🤖 AI ВЕРДИКТ: COMPLIANT")
                        elif ai_verdict == 'PARTIAL':
                            st.warning(f"🤖 AI ВЕРДИКТ: PARTIAL")
                        elif ai_verdict == 'NOT_FOUND':
                            st.error(f"🤖 AI ВЕРДИКТ: NOT_FOUND")
                        else:
                            st.info(f"🤖 AI ВЕРДИКТ: UNCLEAR")

                        if explanation:
                            st.markdown("**Объяснение AI:**")
                            st.info(explanation)

                elif not api_key:
                    st.info("ℹ️ Введите API-ключ в боковой панели, чтобы увидеть AI-анализ")
        else:
            st.info("📤 Загрузите текстовый документ для проверки")


# ============================================================
# ГЛАВНАЯ ТОЧКА ВХОДА
# ============================================================

def main():
    st.set_page_config(
        page_title="Legal QA System",
        page_icon="⚖️",
        layout="wide"
    )

    st.title("⚖️ Legal QA System")
    st.caption("Проверка документов и сравнение версий закона")

    tab1, tab2 = st.tabs([
        "📄 Проверка документа",
        "📊 Сравнение версий",
    ])

    with tab1:
        render_block1()

    with tab2:
        from src.blocks.block2_compare.ui_compare import render as render_block2
        render_block2()


def main():
    st.set_page_config(
        page_title="Legal QA System",
        page_icon="⚖️",
        layout="wide"
    )

    st.title("⚖️ Legal QA System")
    st.caption("Проверка документов и сравнение версий закона")

    tab1, tab2 = st.tabs([
        "📄 Проверка документа",
        "📊 Сравнение версий",
    ])

    with tab1:
        render_block1()

    with tab2:
        from src.blocks.block2_compare.ui_compare import render as render_block2
        render_block2()


if __name__ == "__main__":
    main()
