#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BM25 SEARCH - Поиск по нормам
Версия для импорта в Codespace
"""

import re
import numpy as np
from typing import List, Dict, Tuple, Optional
from rank_bm25 import BM25Okapi


class BM25Search:
    """
    BM25 поиск по нормам
    """
    
    def __init__(self, norm_ids: List[str], norm_texts: List[str]):
        """
        Args:
            norm_ids: Список ID норм
            norm_texts: Список текстов норм
        """
        self.norm_ids = norm_ids
        self.norm_texts = norm_texts
        self.bm25_model = None
    
    def _clean_text(self, text: str) -> str:
        """Очищает текст от лишних символов"""
        text = re.sub(r'^\d+\.\d*\s*', '', text)
        text = re.sub(r'^\d+\)\s*', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def build_index(self):
        """Строит BM25 индекс"""
        cleaned_texts = [self._clean_text(text) for text in self.norm_texts]
        tokenized_corpus = [text.lower().split() for text in cleaned_texts]
        self.bm25_model = BM25Okapi(tokenized_corpus)
        print(f"✅ BM25 индекс построен для {len(self.norm_ids)} норм")
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Поиск по запросу
        
        Args:
            query: Текст запроса
            top_k: Количество результатов
        
        Returns:
            Список (norm_id, score)
        """
        if self.bm25_model is None:
            raise ValueError("BM25 индекс не построен. Сначала вызовите build_index()")
        
        tokenized_query = query.lower().split()
        scores = self.bm25_model.get_scores(tokenized_query)
        sorted_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.norm_ids[i], scores[i]) for i in sorted_indices]
    
    def search_with_details(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Поиск с деталями
        
        Returns:
            Список словарей с norm_id, score, text
        """
        results = self.search(query, top_k)
        return [
            {
                'norm_id': norm_id,
                'score': float(score),
                'text': self.norm_texts[self.norm_ids.index(norm_id)]
            }
            for norm_id, score in results
        ]