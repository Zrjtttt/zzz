#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CHECK VERIFIER - Проверка документов на соответствие требованиям
Версия 3.0 (с исправленной логикой R4, PARTIAL и UNCLEAR)
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class CheckVerifier:
    """
    Проверяет документ на соответствие требованиям из checks.json
    """
    
    def __init__(self, checks_path: str):
        """
        Args:
            checks_path: путь к файлу checks.json
        """
        with open(checks_path, 'r', encoding='utf-8') as f:
            self.checks_data = json.load(f)
        
        self.check = self.checks_data['check_001']
        self.requirements = self.check['requirements']
    
    def verify(self, document_path: str) -> Dict:
        """
        Проверяет документ и возвращает результат
        
        Args:
            document_path: путь к текстовому документу
        
        Returns:
            Словарь с результатами проверки
        """
        # Читаем документ
        with open(document_path, 'r', encoding='utf-8') as f:
            document_text = f.read()
        
        results = {}
        
        # Проверяем каждое требование
        for req_id, req_data in self.requirements.items():
            results[req_id] = self._check_requirement(req_id, req_data, document_text)
        
        # Определяем общий вердикт
        verdict = self._determine_verdict(results)
        
        return {
            'document': document_path,
            'requirements': results,
            'verdict': verdict
        }
    
    def _check_requirement(self, req_id: str, req_data: Dict, document_text: str) -> Dict:
        """
        Проверяет одно требование в документе
        """
        description = req_data['description']
        required_facts = req_data['required_facts']
        evidence_scope = req_data['evidence_scope']
        verification = req_data['verification']
        
        # Извлекаем факты из документа
        facts = self._extract_facts(document_text, required_facts, req_id)
        
        # Проверяем соответствие
        result = self._apply_verification(facts, verification)
        
        return {
            'description': description,
            'facts': facts,
            'result': result
        }
    
    def _extract_facts(self, document_text: str, required_facts: Dict, req_id: str = None) -> Dict:
        """
        Извлекает факты из документа (нормализованные значения)
        """
        facts = {}
        
        for fact_key, fact_value in required_facts.items():
            if fact_key == 'action':
                # ДЛЯ R4: ищем ТОЛЬКО документирование
                if req_id == 'R4':
                    document_patterns = [
                        r'фиксир[уо]',
                        r'документир[уо]',
                        r'регистрир[уо]',
                    ]
                    found = None
                    for pattern in document_patterns:
                        if re.search(pattern, document_text, re.IGNORECASE):
                            found = 'document'
                            break
                    facts['action'] = found
                else:
                    # ДЛЯ ВСЕХ ОСТАЛЬНЫХ: ищем обновление
                    action_map = {
                        'update': [
                            r'обновля[ею]т?',
                            r'актуализир[уо]',
                            r'пересматрива[ею]т?',
                        ],
                        'document': [
                            r'фиксир[уо]',
                            r'документир[уо]',
                            r'регистрир[уо]',
                        ],
                        'store': [
                            r'хранят?',
                            r'сохраня[ею]т?',
                        ]
                    }
                    found = None
                    for action_type, patterns in action_map.items():
                        for pattern in patterns:
                            if re.search(pattern, document_text, re.IGNORECASE):
                                found = action_type
                                break
                        if found:
                            break
                    facts['action'] = found
            
            elif fact_key == 'object':
                # Маппинг объектов
                object_map = {
                    'beneficiary_information': [
                        r'информаци[юи] о бенефициарн',
                        r'сведени[яй] о бенефициарн',
                        r'бенефициарн.*информаци',
                        r'данн[ые] о бенефициарн',
                    ],
                    'received_information': [
                        r'полученн[ая] информаци[яи]',
                        r'поступивш[ая] информаци[яи]',
                    ],
                    'relevant_information': [
                        r'соответств[у]ющ[ая] информаци[яи]',
                        r'необходим[ая] информаци[яи]',
                    ]
                }
                
                found = None
                for obj_type, patterns in object_map.items():
                    for pattern in patterns:
                        if re.search(pattern, document_text, re.IGNORECASE):
                            found = obj_type
                            break
                    if found:
                        break
                
                # Если ничего не найдено, проверяем отдельно
                if not found:
                    if re.search(r'бенефициарн', document_text, re.IGNORECASE):
                        found = 'beneficiary_information'
                    elif re.search(r'информаци', document_text, re.IGNORECASE):
                        found = 'information'
                
                facts['object'] = found
            
            elif fact_key == 'frequency':
                # Извлекаем периодичность в месяцах
                frequency = None
                
                # Чёткие паттерны
                if re.search(r'ежегодн[оа]|раз в год|кажд[ы]й год|не реже одного раза в год', document_text, re.IGNORECASE):
                    frequency = 12
                elif re.search(r'ежемесячн[оа]|кажд[ы]й месяц|раз в месяц', document_text, re.IGNORECASE):
                    frequency = 1
                elif re.search(r'ежеквартальн[оа]|кажд[ы]й квартал|раз в квартал', document_text, re.IGNORECASE):
                    frequency = 3
                elif re.search(r'кажд[ы]е полгода|раз в полгода', document_text, re.IGNORECASE):
                    frequency = 6
                elif re.search(r'регулярн[оа]|периодическ[и]', document_text, re.IGNORECASE):
                    frequency = None  # UNCLEAR
                else:
                    frequency = None  # NOT_FOUND
                
                facts['frequency'] = frequency
            
            elif fact_key == 'condition':
                # Ищем условия
                if 'on_change' in str(fact_value):
                    condition_patterns = [
                        r'при изменени[ия]',
                        r'в случае изменени[яи]',
                        r'изменени[яй] сведени[йя]',
                        r'при необходимости',
                    ]
                    found = None
                    for pattern in condition_patterns:
                        if re.search(pattern, document_text, re.IGNORECASE):
                            if 'при изменени' in pattern or 'в случае изменени' in pattern or 'изменени' in pattern:
                                found = 'on_change'
                            else:
                                found = 'unclear'
                            break
                    facts['condition'] = found
                else:
                    facts['condition'] = None
            
            else:
                # Для других полей
                facts[fact_key] = None
        
        return facts
    
    def _apply_verification(self, facts: Dict, verification: Dict) -> str:
        """
        Применяет логику проверки к фактам
        """
        # Проверяем COMPLIANT
        if self._matches_condition(facts, verification.get('COMPLIANT', {})):
            return 'COMPLIANT'
        
        # Проверяем PARTIAL
        if self._matches_condition(facts, verification.get('PARTIAL', {})):
            return 'PARTIAL'
        
        # Проверяем NOT_FOUND
        if self._matches_condition(facts, verification.get('NOT_FOUND', {})):
            return 'NOT_FOUND'
        
        # Проверяем UNCLEAR
        if self._matches_condition(facts, verification.get('UNCLEAR', {})):
            return 'UNCLEAR'
        
        return 'NOT_FOUND'
    
    def _matches_condition(self, facts: Dict, condition: Dict) -> bool:
        """
        Проверяет, соответствуют ли факты условию
        """
        if not condition:
            return False
        
        if 'all' in condition:
            # Все условия должны выполняться
            for cond in condition['all']:
                if not self._check_single_condition(facts, cond):
                    return False
            return True
        
        elif 'any' in condition:
            # Хотя бы одно условие должно выполняться
            for cond in condition['any']:
                if self._check_single_condition(facts, cond):
                    return True
            return False
        
        elif 'exactly_one' in condition:
            # Ровно одно условие должно выполняться
            count = 0
            for cond in condition['exactly_one']:
                if self._check_single_condition(facts, cond):
                    count += 1
            return count == 1
        
        elif 'condition' in condition:
            # Специальные условия
            if condition['condition'] == 'evidence_is_ambiguous':
                return False
            if condition['condition'] == 'frequency_is_ambiguous':
                return False
            if condition['condition'] == 'on_change_found_but_action_or_object_incomplete':
                return False
            return True
        
        return False
    
    def _check_single_condition(self, facts: Dict, cond: Dict) -> bool:
        """
        Проверяет одно условие
        """
        field = cond.get('field')
        if not field:
            return False
        
        # Получаем значение из фактов
        value = facts.get(field)
        
        # Проверяем not_found
        if cond.get('not_found'):
            return value is None
        
        # Проверяем equals
        if 'equals' in cond:
            return value == cond['equals']
        
        # Проверяем less_than_or_equal (для частоты)
        if 'less_than_or_equal' in cond:
            if value is None:
                return False
            return value <= cond['less_than_or_equal']
        
        # Проверяем greater_than (для частоты)
        if 'greater_than' in cond:
            if value is None:
                return False
            return value > cond['greater_than']
        
        return False
    
    def _determine_verdict(self, results: Dict) -> str:
        """
        Определяет общий вердикт на основе результатов по требованиям
        """
        statuses = [r['result'] for r in results.values()]
        
        all_compliant = all(s == 'COMPLIANT' for s in statuses)
        any_compliant = any(s == 'COMPLIANT' for s in statuses)
        any_partial = any(s == 'PARTIAL' for s in statuses)
        any_not_found = any(s == 'NOT_FOUND' for s in statuses)
        any_unclear = any(s == 'UNCLEAR' for s in statuses)
        
        if all_compliant:
            return 'COMPLIANT'
        
        if any_unclear:
            return 'UNCLEAR'
        
        if any_partial:
            return 'PARTIAL'
        
        # Если есть хоть одно COMPLIANT, а остальные NOT_FOUND → PARTIAL
        if any_compliant and any_not_found:
            return 'PARTIAL'
        
        if any_not_found:
            return 'NOT_FOUND'
        
        return 'NOT_FOUND'


def main():
    """Тестирование на 4 документах"""
    verifier = CheckVerifier('data/115-fz/processed/checks.json')
    
    documents = [
        ('data/test_documents/document_A_compliant.txt', 'COMPLIANT'),
        ('data/test_documents/document_B_partial.txt', 'PARTIAL'),
        ('data/test_documents/document_C_not_found.txt', 'NOT_FOUND'),
        ('data/test_documents/document_D_unclear.txt', 'PARTIAL'),
    ]
    
    print("\n" + "="*60)
    print("ПРОВЕРКА ДОКУМЕНТОВ")
    print("="*60)
    
    for doc_path, expected in documents:
        print(f"\n📄 {doc_path}")
        print(f"   Ожидается: {expected}")
        
        result = verifier.verify(doc_path)
        
        print(f"\n   📋 РЕЗУЛЬТАТЫ ПО ТРЕБОВАНИЯМ:")
        for req_id, req_result in result['requirements'].items():
            status = req_result['result']
            emoji = '✅' if status == 'COMPLIANT' else '⚠️' if status == 'PARTIAL' else '❌' if status == 'NOT_FOUND' else '❓'
            print(f"      {emoji} {req_id}: {status}")
            print(f"         Факты: {req_result['facts']}")
        
        print(f"\n   📊 ВЕРДИКТ: {result['verdict']}")
        print(f"   {'✅' if result['verdict'] == expected else '❌'} Ожидалось: {expected}")


if __name__ == "__main__":
    main()