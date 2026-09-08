#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LEGAL QA SYSTEM - Точка входа
Статья 6.1 115-ФЗ
Версия: 1.0
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.norm_loader import NormLoader
from src.search.bm25 import BM25Search
from src.understanding.question_frame import QuestionFrame
from src.graph.legal_graph import LegalGraph
from src.router.router import Router
from src.interface.chat import ChatInterface


def main():
    parser = argparse.ArgumentParser(description='Legal QA System')
    parser.add_argument('--article', type=str, default='6.1',
                        help='Номер статьи (например: 6.1)')
    parser.add_argument('--mode', type=str, default='chat',
                        choices=['chat', 'test', 'pipeline', 'info'],
                        help='Режим работы: chat, test, pipeline, info')
    parser.add_argument('--question', type=str, default=None,
                        help='Один вопрос для тестирования')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                        help='Путь к конфигурационному файлу')
    
    args = parser.parse_args()
    
    # ============================================================
    # 1. ЗАГРУЗКА ДАННЫХ
    # ============================================================
    
    print("="*60)
    print("LEGAL QA SYSTEM")
    print("="*60)
    print(f"\n📂 Статья: {args.article}")
    print(f"📂 Режим: {args.mode}")
    
    # Пути к данным
    base_dir = Path(__file__).parent
    data_dir = base_dir / 'data' / '115-fz' / 'processed'
    
    norms_file = data_dir / 'norms.json'
    gold_file = data_dir / 'gold_set.json'
    graph_file = data_dir / 'graph.json'
    
    # Проверяем наличие файлов
    if not norms_file.exists():
        print(f"\n❌ Файл не найден: {norms_file}")
        print("   Сначала загрузите данные из Colab")
        return
    
    print(f"✅ Нормы: {norms_file}")
    
    # Загружаем нормы
    with open(norms_file, 'r', encoding='utf-8') as f:
        norms_data = json.load(f)
    
    norms = norms_data.get('norms', {})
    norm_ids = list(norms.keys())
    norm_texts = [norms[nid]['original_text'] for nid in norm_ids]
    
    print(f"✅ Загружено норм: {len(norms)}")
    
    # Загружаем Gold Set (если есть)
    questions = []
    if gold_file.exists():
        with open(gold_file, 'r', encoding='utf-8') as f:
            gold_data = json.load(f)
        questions = gold_data.get('questions', [])
        print(f"✅ Загружено вопросов: {len(questions)}")
    
    # Загружаем граф (если есть)
    graph = None
    if graph_file.exists():
        with open(graph_file, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        graph = graph_data.get('graph', {})
        print(f"✅ Граф загружен")
    
    # ============================================================
    # 2. ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ
    # ============================================================
    
    print("\n🔧 Инициализация компонентов...")
    
    # BM25
    bm25 = BM25Search(norm_ids, norm_texts)
    bm25.build_index()
    
    # Question Frame
    qf = QuestionFrame()
    
    # Router
    router = Router(norm_ids, norm_texts, norms, bm25, qf, graph)
    
    # Chat Interface
    chat = ChatInterface(router)
    
    # ============================================================
    # 3. ЗАПУСК В ЗАВИСИМОСТИ ОТ РЕЖИМА
    # ============================================================
    
    if args.mode == 'info':
        # Информация о системе
        print("\n" + "="*60)
        print("ИНФОРМАЦИЯ О СИСТЕМЕ")
        print("="*60)
        print(f"\n📋 Статья: 6.1 115-ФЗ")
        print(f"📋 Всего норм: {len(norms)}")
        print(f"📋 ID норм: {norm_ids}")
        print(f"📋 Всего вопросов: {len(questions)}")
        print("\n📋 Нормы:")
        for nid in norm_ids:
            text = norms[nid]['original_text'][:80] + "..."
            print(f"   {nid}: {text}")
        
        if graph:
            print(f"\n📋 Граф: {len(graph.get('edges', {}))} связей")
    
    elif args.mode == 'test':
        # Тестирование на Gold Set
        if not questions:
            print("\n❌ Нет Gold Set для тестирования")
            return
        
        print("\n" + "="*60)
        print("ТЕСТИРОВАНИЕ")
        print("="*60)
        
        results = router.evaluate(questions)
        
        print(f"\n📊 Результаты:")
        print(f"   Top-1 Accuracy: {results['metrics']['top1_accuracy']:.2%}")
        print(f"   MRR: {results['metrics']['mrr']:.2%}")
        print(f"   Recall@5: {results['metrics']['recall@5']:.2%}")
        print(f"   Средний ранг: {results['metrics']['avg_rank']:.2f}")
        
        # Сохраняем результаты
        output_file = data_dir / 'test_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Результаты сохранены: {output_file}")
    
    elif args.mode == 'pipeline':
        # Полный пайплайн
        print("\n" + "="*60)
        print("ЗАПУСК ПАЙПЛАЙНА")
        print("="*60)
        
        if args.question:
            # Один вопрос
            answer = router.answer(args.question)
            print(f"\n📌 Вопрос: {args.question}")
            print(f"✅ Ответ: {answer['answer']}")
            print(f"📋 Источник: {answer['source']}")
            print(f"📊 Уверенность: {answer['confidence']}")
            print(f"⚡ Путь: {answer['path']}")
        else:
            # Все вопросы из Gold Set
            if not questions:
                print("\n❌ Нет Gold Set")
                return
            
            print("\n📋 Прогон всех вопросов:")
            for q in questions:
                answer = router.answer(q['text'])
                status = "✅" if answer['rank'] == 1 else "⚠️"
                print(f"   {status} {q['id']}: ранг {answer['rank']} ({answer['path']})")
    
    elif args.mode == 'chat':
        # Интерактивный чат
        chat.start()


if __name__ == "__main__":
    main()