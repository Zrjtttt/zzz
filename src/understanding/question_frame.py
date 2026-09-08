#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
QUESTION FRAME - Анализ структуры вопроса
Версия для импорта в Codespace
"""

import re
import json
from typing import List, Dict, Tuple, Optional
import numpy as np
from rank_bm25 import BM25Okapi


class QuestionFrame:
    """
    Анализирует структуру вопроса:
    - intent (намерение)
    - subject, action, legal_effect, object
    - специальные признаки (exception, negation, temporal)
    """
    
    def __init__(self):
        # Паттерны для определения intent
        self.intent_patterns = {
            'subject': [
                r'кто', r'какое лицо', r'какие лица', r'кем', r'для кого'
            ],
            'action': [
                r'что должна?|что должны?|что обязан|что обязано',
                r'какие меры', r'какие действия'
            ],
            'deadline': [
                r'как часто', r'в какой срок', r'сколько лет', r'период',
                r'не реже', r'не менее', r'в течение'
            ],
            'exception': [
                r'освобождается', r'не распространяется', r'исключение',
                r'на кого не', r'для кого не'
            ],
            'definition': [
                r'кто считается', r'что означает', r'что понимается',
                r'под .+ понимается'
            ],
            'recipient': [
                r'перед какими', r'кому', r'каким органам', r'по запросу'
            ],
            'extension': [
                r'распространяются', r'распространяется', r'на кого распространяется'
            ],
            'multi_hop': [
                r'и в какой срок', r'и что', r'какие органы.*и что',
                r'что.*и в какой срок'
            ],
            'negative': [
                r'является ли.*нарушением', r'обязаны ли',
                r'является ли.*не', r'не является'
            ]
        }
        
        # Паттерны для извлечения сущностей
        self.entity_patterns = {
            'subject': {
                'юридическое лицо': r'юридическ(?:ое|ого|ому|им) лиц(?:о|а|у|ом)',
                'учредители и участники': r'учредител(?:и|ей|ям)|участник(?:и|ов|ам)',
                'информация': r'информаци(?:я|и|ю|ей)',
                'положения пунктов 1-7': r'положения пунктов',
                'бенефициарный владелец': r'бенефициарн(?:ый|ого|ому|ым) владел(?:ец|ьца|ьцу|ьцем)'
            },
            'action': {
                'располагать информацией': r'располагать информаци(?:ей|и)',
                'принимать меры': r'принимать меры',
                'обновлять информацию': r'обновлять информаци(?:ю|и)',
                'документально фиксировать': r'документально фиксировать',
                'хранить информацию': r'хранить информаци(?:ю|и)',
                'запрашивать информацию': r'запрашивать информаци(?:ю|и)',
                'представлять информацию': r'представлять информаци(?:ю|и)',
                'раскрывается': r'раскрыва(?:ется|ются)',
                'распространяются': r'распространя(?:ется|ются)'
            },
            'legal_effect': {
                'obligation': r'обязан|обязаны|обязано',
                'right': r'вправе',
                'exception': r'освобождается|не распространяется',
                'definition': r'понимается|считается',
                'disclosure': r'раскрывается',
                'extension': r'распространяются'
            },
            'object': {
                'бенефициарные владельцы': r'бенефициарн(?:ых|ые|ым|ыми) владел(?:ьцев|ьцам|ьцами)',
                'сведения': r'сведени(?:й|я|ям|ями)',
                'информация': r'информаци(?:я|и|ю|ей)',
                'органы': r'орган(?:а|ов|ам|ами)',
                'меры': r'мер(?:ы|у|ами|ах)'
            }
        }
    
    def analyze(self, question_text: str, question_type: str = None) -> Dict:
        """
        Анализирует вопрос и возвращает структуру
        """
        result = {
            'original_text': question_text,
            'intent': None,
            'subject': None,
            'action': None,
            'legal_effect': None,
            'object': None,
            'temporal': False,
            'exception': False,
            'definition': False,
            'negation': False,
            'multi_hop': False,
            'confidence': {}
        }
        
        # 1. Определяем intent
        intent = self._detect_intent(question_text, question_type)
        result['intent'] = intent
        result['confidence']['intent'] = 'high' if intent else 'low'
        
        # 2. Извлекаем сущности
        result['subject'] = self._extract_entity(question_text, 'subject')
        result['action'] = self._extract_entity(question_text, 'action')
        result['legal_effect'] = self._extract_entity(question_text, 'legal_effect')
        result['object'] = self._extract_entity(question_text, 'object')
        
        # 3. Специальные признаки
        result['temporal'] = bool(re.search(r'срок|период|год|лет|дней|регулярно', question_text))
        result['exception'] = bool(re.search(r'освобождается|не распространяется|исключение', question_text))
        result['definition'] = bool(re.search(r'понимается|считается|означает', question_text))
        result['negation'] = bool(re.search(r'не является|не распространяется|не нарушением', question_text))
        result['multi_hop'] = bool(re.search(r'и.*срок|и.*что|какие.*и', question_text))
        
        # 4. Если тип вопроса указан в Gold Set — используем его
        if question_type:
            result['gold_type'] = question_type
            if not result['intent']:
                result['intent'] = question_type
        
        return result
    
    def _detect_intent(self, text: str, question_type: str = None) -> Optional[str]:
        """Определяет намерение вопроса"""
        text_lower = text.lower()
        
        # Если есть тип из Gold Set — используем его как подсказку
        if question_type and question_type in self.intent_patterns:
            for pattern in self.intent_patterns[question_type]:
                if re.search(pattern, text_lower):
                    return question_type
        
        # Ищем по всем паттернам
        scores = {}
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1
            if score > 0:
                scores[intent] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return None
    
    def _extract_entity(self, text: str, entity_type: str) -> Optional[str]:
        """Извлекает сущность из текста"""
        text_lower = text.lower()
        
        if entity_type not in self.entity_patterns:
            return None
        
        for entity_name, pattern in self.entity_patterns[entity_type].items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                return entity_name
        
        return None
    
    def get_search_strategy(self, frame: Dict) -> Dict:
        """
        Определяет стратегию поиска на основе Question Frame
        """
        strategy = {
            'priority_fields': [],
            'boost_exception': False,
            'boost_definition': False,
            'boost_temporal': False,
            'boost_negation': False,
            'required_fields': []
        }
        
        intent = frame.get('intent')
        
        if intent == 'subject':
            strategy['priority_fields'].append('subject')
            if frame.get('subject'):
                strategy['required_fields'].append('subject')
        
        elif intent == 'action':
            strategy['priority_fields'].append('action')
            if frame.get('action'):
                strategy['required_fields'].append('action')
        
        elif intent == 'deadline':
            strategy['priority_fields'].append('temporal')
            strategy['boost_temporal'] = True
        
        elif intent == 'exception':
            strategy['priority_fields'].append('exception')
            strategy['boost_exception'] = True
            strategy['required_fields'].append('exception')
        
        elif intent == 'definition':
            strategy['priority_fields'].append('definition')
            strategy['boost_definition'] = True
            strategy['required_fields'].append('definition')
        
        elif intent == 'recipient':
            strategy['priority_fields'].append('object')
            strategy['priority_fields'].append('subject')
            if frame.get('object'):
                strategy['required_fields'].append('object')
        
        elif intent == 'extension':
            strategy['priority_fields'].append('extension')
        
        elif intent == 'multi_hop':
            strategy['priority_fields'].append('action')
            strategy['priority_fields'].append('temporal')
            strategy['boost_temporal'] = True
        
        elif intent == 'negative':
            strategy['priority_fields'].append('negation')
            strategy['boost_negation'] = True
        
        # Всегда учитываем legal_effect, если он определён
        if frame.get('legal_effect'):
            strategy['priority_fields'].append('legal_effect')
        
        return strategy


class StructuredRetrievalWithFrame:
    """
    Поиск с использованием Question Frame
    """
    
    def __init__(self, norm_ids: List[str], norm_texts: List[str], norm_fields: Dict):
        self.norm_ids = norm_ids
        self.norm_texts = norm_texts
        self.norm_fields = norm_fields
        self.question_frame = QuestionFrame()
        self.bm25_model = None
    
    def build_bm25(self):
        """Строит BM25 индекс"""
        tokenized_corpus = [text.lower().split() for text in self.norm_texts]
        self.bm25_model = BM25Okapi(tokenized_corpus)
        print("✅ BM25 индекс построен")
    
    def search_bm25(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """Поиск через BM25"""
        tokenized_query = query.lower().split()
        scores = self.bm25_model.get_scores(tokenized_query)
        sorted_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.norm_ids[i], scores[i]) for i in sorted_indices]
    
    def calculate_structured_score(self, norm_id: str, frame: Dict, strategy: Dict) -> Tuple[float, List[str]]:
        """
        Вычисляет структурный вес с учётом стратегии
        """
        norm = self.norm_fields.get(norm_id, {})
        score = 0.0
        matches = []
        
        field_weights = {
            'subject': 3.0,
            'action': 2.5,
            'legal_effect': 2.0,
            'object': 1.5,
            'temporal': 2.0,
            'exception': 3.0,
            'definition': 2.5,
            'negation': 2.0
        }
        
        # Проверяем приоритетные поля
        for field in strategy.get('priority_fields', []):
            if field == 'temporal':
                if norm.get('temporal') is not None:
                    score += field_weights.get(field, 2.0) * 1.5
                    matches.append(f'temporal:{norm["temporal"]}')
            elif field == 'exception':
                if norm.get('exception'):
                    score += field_weights.get(field, 3.0)
                    matches.append('exception')
            elif field == 'definition':
                if norm.get('definition'):
                    score += field_weights.get(field, 2.5)
                    matches.append('definition')
            elif field == 'negation':
                if norm.get('negation'):
                    score += field_weights.get(field, 2.0)
                    matches.append('negation')
            else:
                norm_value = norm.get(field)
                frame_value = frame.get(field)
                if norm_value and frame_value:
                    if isinstance(norm_value, list):
                        if frame_value in norm_value:
                            score += field_weights.get(field, 2.0)
                            matches.append(f'{field}:{frame_value}')
                    else:
                        if norm_value == frame_value:
                            score += field_weights.get(field, 2.0)
                            matches.append(f'{field}:{frame_value}')
        
        # Проверяем обязательные поля
        for field in strategy.get('required_fields', []):
            if field not in [m.split(':')[0] for m in matches]:
                score -= 2.0
        
        # Дополнительные бонусы
        if strategy.get('boost_exception') and norm.get('exception'):
            score += 1.0
            matches.append('exception_boost')
        
        if strategy.get('boost_temporal') and norm.get('temporal'):
            score += 1.0
            matches.append('temporal_boost')
        
        if strategy.get('boost_definition') and norm.get('definition'):
            score += 1.0
            matches.append('definition_boost')
        
        if strategy.get('boost_negation') and norm.get('negation'):
            score += 1.0
            matches.append('negation_boost')
        
        return score, matches
    
    def search(self, question_text: str, question_type: str = None, top_k: int = 10) -> Dict:
        """
        Полный поиск с Question Frame
        """
        # 1. Анализируем вопрос
        frame = self.question_frame.analyze(question_text, question_type)
        strategy = self.question_frame.get_search_strategy(frame)
        
        # 2. BM25 поиск
        bm25_results = self.search_bm25(question_text, top_k=top_k * 3)
        
        # 3. Структурное ранжирование
        scored_results = []
        for norm_id, bm25_score in bm25_results:
            struct_score, matches = self.calculate_structured_score(norm_id, frame, strategy)
            total_score = bm25_score * 1.0 + struct_score * 0.5
            scored_results.append({
                'norm_id': norm_id,
                'total_score': total_score,
                'bm25_score': bm25_score,
                'struct_score': struct_score,
                'matches': matches,
                'frame': frame,
                'strategy': strategy
            })
        
        scored_results.sort(key=lambda x: x['total_score'], reverse=True)
        
        return {
            'question': question_text,
            'question_type': question_type,
            'frame': frame,
            'strategy': strategy,
            'top_results': scored_results[:top_k]
        }
    
    def evaluate(self, questions: List[Dict], top_k: int = 10) -> Dict:
        """
        Оценка системы с Question Frame
        """
        results = []
        
        for q in questions:
            q_id = q['id']
            q_text = q['text']
            q_type = q['type']
            correct_norms = set(q['correct_norm_ids'])
            
            search_result = self.search(q_text, q_type, top_k=top_k)
            retrieved_norms = [r['norm_id'] for r in search_result['top_results']]
            
            rank = None
            for i, norm_id in enumerate(retrieved_norms):
                if norm_id in correct_norms:
                    rank = i + 1
                    break
            
            results.append({
                'question_id': q_id,
                'question_text': q_text,
                'question_type': q_type,
                'frame': search_result['frame'],
                'correct_norms': list(correct_norms),
                'retrieved_norms': retrieved_norms[:5],
                'rank': rank,
                'is_found': rank is not None,
                'matches': [r['matches'] for r in search_result['top_results'][:5]]
            })
        
        # Метрики
        total = len(results)
        
        recall_at_k = {}
        for k in [1, 3, 5, 10]:
            found = sum(1 for r in results if r['rank'] is not None and r['rank'] <= k)
            recall_at_k[f'recall@{k}'] = found / total
        
        top1_accuracy = sum(1 for r in results if r['rank'] == 1) / total
        mrr = sum(1.0 / r['rank'] if r['rank'] is not None else 0 for r in results) / total
        ranks = [r['rank'] for r in results if r['is_found']]
        avg_rank = np.mean(ranks) if ranks else None
        
        metrics = {
            **recall_at_k,
            'top1_accuracy': top1_accuracy,
            'mrr': mrr,
            'avg_rank': avg_rank
        }
        
        return {
            'method': 'question_frame_retrieval',
            'metrics': metrics,
            'per_question': results
        }