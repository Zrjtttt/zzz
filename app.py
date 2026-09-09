#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LEGAL QA SYSTEM - Упрощённый интерфейс
Ручной режим (слева) + Автоматический режим (справа)
"""

import streamlit as st
import json
import sys
import os
from pathlib import Path

# Добавляем src в путь
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
    """Загружает систему"""
    
    data_dir = Path(__file__).parent / 'data' / '115-fz' / 'processed'
    norms_file = data_dir / 'norms.json'
    gold_file = data_dir / 'gold_set.json'
    graph_file = data_dir / 'graph.json'
    checks_file = data_dir / 'checks.json'
    
    # Загружаем нормы
    with open(norms_file, 'r', encoding='utf-8') as f:
        norms_data = json.load(f)
    
    norms = norms_data.get('norms', {})
    norm_ids = list(norms.keys())
    norm_texts = [norms[nid]['original_text'] for nid in norm_ids]
    
    # Загружаем граф
    graph = None
    if graph_file.exists():
        with open(graph_file, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        graph = graph_data.get('graph', {})
    
    # Инициализируем компоненты
    bm25 = BM25Search(norm_ids, norm_texts)
    bm25.build_index()
    
    qf = QuestionFrame()
    
    router = Router(norm_ids, norm_texts, norms, bm25, qf, graph)
    
    # Загружаем Check Verifier
    verifier = None
    if checks_file.exists():
        verifier = CheckVerifier(str(checks_file))
    
    return router, norms, verifier


# ============================================================
# ВОПРОСЫ ДЛЯ ЧЕК-ЛИСТА
# ============================================================

QUESTIONS = [
    {
        "id": "q1",
        "text": "Кто является бенефициарным владельцем?",
        "norm_id": "8",
        "expected": "Физическое лицо, владеющее более 25% капитала или контролирующее действия"
    },
    {
        "id": "q2",
        "text": "Кто обязан раскрывать информацию о бенефициарных владельцах?",
        "norm_id": "1",
        "expected": "Юридическое лицо"
    },
    {
        "id": "q3",
        "text": "Как часто нужно обновлять информацию о бенефициарных владельцах?",
        "norm_id": "3.1",
        "expected": "Не реже одного раза в год, а также при изменении сведений"
    },
    {
        "id": "q4",
        "text": "Сколько лет нужно хранить информацию о бенефициарных владельцах?",
        "norm_id": "3.2",
        "expected": "Не менее пяти лет"
    },
    {
        "id": "q5",
        "text": "Перед какими органами нужно отчитываться о бенефициарных владельцах?",
        "norm_id": "6",
        "expected": "Уполномоченный орган, налоговые органы, федеральный орган по регистрации НКО"
    },
]


# ============================================================
# ОСНОВНОЙ ИНТЕРФЕЙС
# ============================================================

def main():
    st.set_page_config(
        page_title="Проверка по статье 6.1",
        page_icon="⚖️",
        layout="wide"
    )
    
    # Заголовок
    st.title("⚖️ Проверка по статье 6.1 115-ФЗ")
    st.caption("Бенефициарные владельцы — требования к документам")
    
    # Загружаем систему
    with st.spinner("Загрузка..."):
        router, norms, verifier = load_system()
    
    # ДВЕ КОЛОНКИ
    col_left, col_right = st.columns(2, gap="large")
    
    # ============================================================
    # ЛЕВАЯ КОЛОНКА: РУЧНОЙ РЕЖИМ
    # ============================================================
    
    with col_left:
        st.subheader("📋 Что требует закон")
        st.caption("Нажмите на вопрос — получите ответ из закона")
        
        # Чек-лист
        for q in QUESTIONS:
            # Кнопка-вопрос
            if st.button(
                f"☑️ {q['text']}",
                key=f"manual_{q['id']}",
                use_container_width=True,
                type="secondary"
            ):
                st.session_state['selected_question'] = q['id']
                st.rerun()
        
        st.divider()
        
        # Ответ на выбранный вопрос
        if 'selected_question' in st.session_state:
            q_id = st.session_state['selected_question']
            q = next((q for q in QUESTIONS if q['id'] == q_id), None)
            
            if q:
                st.markdown("**Ответ:**")
                st.success(q['expected'])
                
                st.caption(f"📌 Источник: норма {q['norm_id']}")
                
                # Показать текст нормы
                norm_text = norms.get(q['norm_id'], {}).get('original_text', '')
                if norm_text:
                    with st.expander("📖 Показать текст нормы"):
                        st.text(norm_text)
        
        st.divider()
        st.caption("💡 Это эталонный ответ из закона. Используйте его для проверки документов вручную.")
    
    # ============================================================
    # ПРАВАЯ КОЛОНКА: АВТОМАТИЧЕСКИЙ РЕЖИМ
    # ============================================================
    
    with col_right:
        st.subheader("📄 Проверка документа")
        st.caption("Загрузите документ — система проверит его автоматически")
        
        # Загрузка файла
        uploaded_file = st.file_uploader(
            "Загрузите документ (TXT)",
            type=['txt'],
            key="document_uploader"
        )
        
        if uploaded_file is not None:
            # Читаем текст документа
            document_text = uploaded_file.read().decode('utf-8')
            
            # Кнопка проверки
            if st.button("🔍 Проверить документ", type="primary", use_container_width=True):
                with st.spinner("Проверка документа..."):
                    # Сохраняем временный файл
                    temp_path = Path("/tmp/uploaded_doc.txt")
                    temp_path.write_text(document_text, encoding='utf-8')
                    
                    # Запускаем проверку
                    result = verifier.verify(str(temp_path))
                    
                    # Показываем результаты
                    st.divider()
                    st.subheader("📊 Результат проверки")
                    
                    # Общий вердикт
                    verdict = result['verdict']
                    if verdict == 'COMPLIANT':
                        st.success("✅ Документ СООТВЕТСТВУЕТ требованиям")
                    elif verdict == 'PARTIAL':
                        st.warning("⚠️ Частичное соответствие")
                    elif verdict == 'NOT_FOUND':
                        st.error("❌ Требования не найдены")
                    else:
                        st.info("❓ Не удалось определить")
                    
                    # Детали по требованиям
                    st.divider()
                    st.caption("Детали проверки:")
                    
                    for req_id, req_result in result['requirements'].items():
                        status = req_result['result']
                        
                        if status == 'COMPLIANT':
                            icon = "✅"
                            color = "green"
                        elif status == 'PARTIAL':
                            icon = "⚠️"
                            color = "orange"
                        elif status == 'NOT_FOUND':
                            icon = "❌"
                            color = "red"
                        else:
                            icon = "❓"
                            color = "gray"
                        
                        st.markdown(f"{icon} **{req_id}:** {req_result['description']}")
                        st.caption(f"   Статус: {status}")
                        
                        # Показать найденные факты
                        facts = req_result['facts']
                        if facts:
                            facts_str = ", ".join([f"{k}: {v}" for k, v in facts.items() if v is not None])
                            if facts_str:
                                st.caption(f"   Найдено: {facts_str}")
                    
                    # Рекомендация
                    st.divider()
                    if verdict == 'COMPLIANT':
                        st.success("✅ Документ полностью соответствует требованиям статьи 6.1")
                    elif verdict == 'PARTIAL':
                        st.info("📌 Рекомендуется доработать документ в соответствии с недостающими требованиями")
                    elif verdict == 'NOT_FOUND':
                        st.error("📌 Документ не содержит необходимых требований. Рекомендуется переработать документ")
                    
                    # Очистка
                    temp_path.unlink(missing_ok=True)
        
        else:
            st.info("📤 Загрузите текстовый документ для проверки")
    
    # ============================================================
    # ПОДВАЛ
    # ============================================================
    
    st.divider()
    st.caption("⚖️ Система проверяет документы по статье 6.1 115-ФЗ. Ручной режим показывает эталонный ответ из закона.")


if __name__ == "__main__":
    main()