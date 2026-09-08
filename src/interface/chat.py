#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CHAT INTERFACE - Консольный чат для Legal QA System
"""

import sys
import os
import json
from typing import Dict, Optional

# Добавляем src в путь, если запускаем отдельно
if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class ChatInterface:
    """
    Простой консольный интерфейс для общения с Legal QA System
    """
    
    def __init__(self, router):
        """
        Args:
            router: Экземпляр Router
        """
        self.router = router
        self.history = []
        self.stats = {
            'total': 0,
            'fast_path': 0,
            'slow_path': 0,
            'slow_graph': 0
        }
    
    def start(self):
        """Запускает интерактивный чат"""
        self._print_header()
        
        while True:
            try:
                # Получаем вопрос
                question = input("\n💬 Вы: ").strip()
                
                # Проверка на выход
                if question.lower() in ['exit', 'quit', 'выход', 'q']:
                    self._print_goodbye()
                    break
                
                # Проверка на пустой вопрос
                if not question:
                    print("   Пожалуйста, задайте вопрос.")
                    continue
                
                # Проверка на команды
                if question.lower() == '/stats':
                    self._print_stats()
                    continue
                
                if question.lower() == '/history':
                    self._print_history()
                    continue
                
                if question.lower() == '/clear':
                    os.system('clear' if os.name == 'posix' else 'cls')
                    self._print_header()
                    continue
                
                # Отправляем вопрос системе
                self._process_question(question)
                
            except KeyboardInterrupt:
                self._print_goodbye()
                break
            except Exception as e:
                print(f"\n❌ Ошибка: {e}")
                continue
    
    def _process_question(self, question: str):
        """Обрабатывает один вопрос"""
        print("\n🤔 Думаю...", end="", flush=True)
        
        # Получаем ответ от роутера
        result = self.router.answer(question)
        
        self.stats['total'] += 1
        
        # Обновляем статистику
        path = result.get('path', 'unknown')
        if 'FAST' in path:
            self.stats['fast_path'] += 1
        elif 'GRAPH' in path:
            self.stats['slow_graph'] += 1
        else:
            self.stats['slow_path'] += 1
        
        # Сохраняем в историю
        self.history.append({
            'question': question,
            'answer': result['answer'][:100] + '...' if len(result['answer']) > 100 else result['answer'],
            'source': result['source'],
            'path': path,
            'confidence': result['confidence']
        })
        
        # Очищаем строку "Думаю..."
        print("\r" + " " * 20 + "\r", end="")
        
        # Выводим ответ
        self._print_answer(result)
    
    def _print_header(self):
        """Печатает заголовок чата"""
        print("="*60)
        print("⚖️  LEGAL QA SYSTEM - ЧАТ")
        print("="*60)
        print("\n📋 Статья 6.1 115-ФЗ")
        print("📋 Версия: 1.0")
        print("\n💡 Команды:")
        print("   /stats   - показать статистику")
        print("   /history - показать историю")
        print("   /clear   - очистить экран")
        print("   exit     - выход")
        print("\n" + "="*60)
        print("Задайте вопрос или введите команду:")
    
    def _print_answer(self, result: Dict):
        """Печатает ответ"""
        answer = result.get('answer', 'Нет ответа')
        source = result.get('source', '')
        confidence = result.get('confidence', 0)
        path = result.get('path', 'unknown')
        explanation = result.get('explanation', '')
        norm_id = result.get('norm_id', '')
        is_exception = result.get('is_exception', False)
        top_5 = result.get('top_5_norms', [])
        
        # Определяем иконку для пути
        path_icon = "⚡" if "FAST" in path else "🐢" if "GRAPH" in path else "🔍"
        
        # Определяем цвет для уверенности
        confidence_pct = confidence * 100
        if confidence_pct >= 90:
            confidence_color = "🟢"
        elif confidence_pct >= 70:
            confidence_color = "🟡"
        else:
            confidence_color = "🔴"
        
        # Выводим ответ
        print("\n" + "="*60)
        print(f"🤖 Ответ:")
        print(f"\n   {answer[:300]}" + ("..." if len(answer) > 300 else ""))
        print(f"\n📋 Источник: {source}")
        print(f"📊 Уверенность: {confidence_color} {confidence_pct:.0f}%")
        print(f"⚡ Путь: {path_icon} {path}")
        
        if explanation:
            print(f"💡 Пояснение: {explanation}")
        
        if is_exception:
            print("⚠️  Это исключение (норма не распространяется на всех)")
        
        if top_5 and len(top_5) > 1:
            print(f"\n📋 TOP-5 норм: {', '.join(top_5[:5])}")
        
        print("="*60)
        print("\n💬 Задайте следующий вопрос (или exit для выхода):")
    
    def _print_stats(self):
        """Печатает статистику"""
        total = self.stats['total']
        if total == 0:
            print("\n📊 Пока нет вопросов.")
            return
        
        print("\n" + "="*60)
        print("📊 СТАТИСТИКА")
        print("="*60)
        print(f"\n   Всего вопросов: {total}")
        print(f"   FAST PATH: {self.stats['fast_path']} ({self.stats['fast_path']/total*100:.1f}%)")
        print(f"   SLOW PATH (GRAPH): {self.stats['slow_graph']} ({self.stats['slow_graph']/total*100:.1f}%)")
        print(f"   SLOW PATH (OTHER): {self.stats['slow_path']} ({self.stats['slow_path']/total*100:.1f}%)")
        
        # Вычисляем среднюю уверенность из истории
        if self.history:
            avg_conf = sum(h['confidence'] for h in self.history) / len(self.history)
            print(f"\n   Средняя уверенность: {avg_conf*100:.1f}%")
        
        print("="*60)
        print("\n💬 Задайте следующий вопрос:")
    
    def _print_history(self):
        """Печатает историю диалога"""
        if not self.history:
            print("\n📋 История пуста.")
            return
        
        print("\n" + "="*60)
        print("📋 ИСТОРИЯ")
        print("="*60)
        
        for i, item in enumerate(self.history, 1):
            print(f"\n{i}. ❓ {item['question']}")
            print(f"   ✅ {item['answer']}")
            print(f"   📋 {item['source']}")
            print(f"   ⚡ {item['path']}")
            print(f"   📊 Уверенность: {item['confidence']*100:.0f}%")
        
        print("="*60)
        print("\n💬 Задайте следующий вопрос:")
    
    def _print_goodbye(self):
        """Печатает сообщение при выходе"""
        print("\n" + "="*60)
        print("👋 До свидания!")
        print("="*60)
        print("\n📊 Итоговая статистика:")
        print(f"   Всего вопросов: {self.stats['total']}")
        if self.stats['total'] > 0:
            print(f"   FAST PATH: {self.stats['fast_path']}/{self.stats['total']} ({self.stats['fast_path']/self.stats['total']*100:.1f}%)")
        print("\n💡 Если есть вопросы — возвращайтесь!")


# ============================================================
# 6. ЗАПУСК ОТДЕЛЬНО (ДЛЯ ТЕСТИРОВАНИЯ)
# ============================================================

if __name__ == "__main__":
    # Путь к данным
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_file = os.path.join(base_dir, 'data', '115-fz', 'processed', 'norms.json')
    
    if not os.path.exists(data_file):
        print(f"❌ Файл не найден: {data_file}")
        print("   Сначала загрузите данные из Colab")
        sys.exit(1)
    
    # Загружаем нормы
    with open(data_file, 'r', encoding='utf-8') as f:
        norms_data = json.load(f)
    
    norms = norms_data.get('norms', {})
    norm_ids = list(norms.keys())
    norm_texts = [norms[nid]['original_text'] for nid in norm_ids]
    
    # Создаём компоненты
    from src.search.bm25 import BM25Search
    from src.understanding.question_frame import QuestionFrame
    from src.router.router import Router
    
    bm25 = BM25Search(norm_ids, norm_texts)
    bm25.build_index()
    
    qf = QuestionFrame()
    
    router = Router(norm_ids, norm_texts, norms, bm25, qf, None)
    
    chat = ChatInterface(router)
    chat.start()