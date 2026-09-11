#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LEGAL QA SYSTEM - Интерфейс с двумя режимами
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


def call_ai_explanation(api_key: str, question: str, expected: str, document_text: str, result: dict) -> str:
    import requests

    req_details = ""
    for req_id, req_result in result.get('requirements', {}).items():
        status = req_result.get('result', 'unknown')
        desc = req_result.get('description', '')
        facts = req_result.get('facts', {})
        facts_str = ", ".join([f"{k}: {v}" for k, v in facts.items() if v is not None])
        req_details += f"\n- {req_id}: {desc} — {status}"
        if facts_str:
            req_details += f" (найдено: {facts_str})"

    verdict = result.get('verdict', 'unknown')

    prompt = f"""Ты — юридический ассистент по статье 6.1 115-ФЗ.

Пользователь проверил документ по вопросу:
"{question}"

Что требует закон:
"{expected}"

Результат проверки: {verdict}

Детали по требованиям:{req_details}

Фрагмент документа (первые 3000 символов):
{document_text[:3000]}

Объясни пользователю простым языком:
1. Почему такой результат (что совпало, что нет)
2. Что именно нужно исправить в документе
3. Дай практическую рекомендацию

Ответ должен быть понятен сотруднику банка, не юристу.
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
            {"role": "system", "content": "Ты — юридический ассистент. Отвечай понятно и структурированно."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=90
        )
        if response.status_code != 200:
            return f"⚠️ Ошибка API: {response.status_code}"
        result_data = response.json()
        return result_data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Ошибка: {str(e)}"


def check_api_key(api_key: str) -> bool:
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


def main():
    st.set_page_config(
        page_title="Проверка по статье 6.1",
        page_icon="⚖️",
        layout="wide"
    )

    st.title("⚖️ Проверка по статье 6.1 115-ФЗ")
    st.caption("Бенефициарные владельцы — требования к документам")

    with st.sidebar:
        st.header("🔑 API-ключ OpenRouter")

        api_key_input = st.text_input(
            "Введите ключ для AI-объяснений:",
            type="password",
            key="api_key_input",
            help="Ключ нужен только для объяснений. Без него всё остальное работает."
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
            st.info("ℹ️ Без ключа AI-объяснения недоступны")

        st.divider()
        st.caption("Левая колонка: ответы из закона")
        st.caption("Правая колонка: проверка документа")

    api_key = st.session_state.get('api_key_checked', '') if st.session_state.get('api_key_valid') else ''

    with st.spinner("Загрузка..."):
        router, norms, verifier = load_system()

    col_left, col_right = st.columns(2, gap="large")

    # ============================================================
    # ЛЕВАЯ КОЛОНКА
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
    # ПРАВАЯ КОЛОНКА
    # ============================================================

    with col_right:
        st.subheader("📄 Проверка документа")
        st.caption("Загрузите документ и выберите вопрос для проверки")

        uploaded_file = st.file_uploader(
            "Загрузите документ (TXT)",
            type=['txt'],
            key="document_uploader_right"
        )

        if uploaded_file is not None:
            document_text = uploaded_file.read().decode('utf-8')
            st.success(f"✅ Загружен: {uploaded_file.name} ({len(document_text)} символов)")

            st.divider()
            st.markdown("**Выберите вопрос для проверки:**")

            question_options = {q['id']: q['text'] for q in QUESTIONS_RIGHT}

            selected_q_id = st.selectbox(
                "Вопрос",
                options=list(question_options.keys()),
                format_func=lambda x: question_options[x],
                key="question_selector"
            )

            if st.button("🔍 Проверить документ", type="primary", use_container_width=True):
                selected_q = next((q for q in QUESTIONS_RIGHT if q['id'] == selected_q_id), None)

                if selected_q is None:
                    st.error("Вопрос не найден")
                else:
                    with st.spinner("Проверка документа..."):
                        st.divider()
                        st.subheader("📊 Результат проверки")

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
                                st.success("✅ ВЕРДИКТ: Документ ПОЛНОСТЬЮ соответствует требованиям")
                            elif verdict == 'PARTIAL':
                                st.warning("⚠️ ВЕРДИКТ: Документ соответствует ЧАСТИЧНО")
                            elif verdict == 'NOT_FOUND':
                                st.error("❌ ВЕРДИКТ: Требования НЕ ВЫПОЛНЕНЫ")
                            else:
                                st.info("❓ ВЕРДИКТ: НЕ УДАЛОСЬ ОДНОЗНАЧНО ОПРЕДЕЛИТЬ")

                            # === КНОПКА "ОБЪЯСНИТЬ" (ИСПРАВЛЕННАЯ) ===
                            st.divider()

                            if api_key:
                                if st.button("🤖 Объяснить результат", use_container_width=True, key="explain_button"):
                                    st.session_state['need_ai_explanation'] = True
                                    st.session_state['ai_explanation'] = None

                                if st.session_state.get('need_ai_explanation'):
                                    with st.status("⏳ Ждите, AI анализирует документ...", expanded=True) as status:
                                        st.write("Отправка запроса в DeepSeek...")
                                        explanation = call_ai_explanation(
                                            api_key,
                                            selected_q['text'],
                                            selected_q['expected'],
                                            document_text,
                                            result
                                        )
                                        st.session_state['ai_explanation'] = explanation
                                        st.session_state['need_ai_explanation'] = False
                                        status.update(label="✅ AI-объяснение готово", state="complete")

                                if st.session_state.get('ai_explanation'):
                                    st.markdown("### 🤖 AI-объяснение:")
                                    st.info(st.session_state['ai_explanation'])
                            else:
                                st.caption("ℹ️ Введите API-ключ в боковой панели, чтобы получить AI-объяснение")
                        else:
                            st.warning("⚠️ Verifier не загружен. Проверьте наличие checks.json")

                        temp_path.unlink(missing_ok=True)
        else:
            st.info("📤 Загрузите текстовый документ для проверки")

    st.divider()
    st.caption("⚖️ Система проверяет документы по статье 6.1 115-ФЗ.")


if __name__ == "__main__":
    main()
