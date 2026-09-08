#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LEGAL GRAPH - Связи между нормами
Версия для импорта в Codespace
"""

from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class LegalGraph:
    """Граф связей между нормами"""
    
    def __init__(self, graph_data: Optional[Dict] = None):
        """
        Инициализация графа
        
        Args:
            graph_data: Данные графа из graph.json (опционально)
        """
        self.nodes = set()
        self.edges = defaultdict(list)
        self.reverse_edges = defaultdict(list)
        self.edge_info = {}
        
        if graph_data:
            self._load_from_dict(graph_data)
    
    def _load_from_dict(self, graph_data: Dict):
        """Загружает граф из словаря"""
        edges = graph_data.get('edges', {})
        for source, targets in edges.items():
            for target, relation, description in targets:
                self.add_edge(source, target, relation, description)
    
    def add_edge(self, source: str, target: str, relation: str, description: str = ""):
        """Добавляет ребро между нормами"""
        self.nodes.add(source)
        self.nodes.add(target)
        self.edges[source].append((target, relation))
        self.reverse_edges[target].append((source, relation))
        self.edge_info[(source, target)] = {'relation': relation, 'description': description}
    
    def get_neighbors(self, node: str, relation: str = None) -> List[Tuple[str, str]]:
        """Возвращает соседей узла с фильтром по типу связи"""
        if relation:
            return [(target, rel) for target, rel in self.edges.get(node, []) if rel == relation]
        return self.edges.get(node, [])
    
    def get_related_norms(self, norm_id: str, relation_types: List[str] = None) -> List[Tuple[str, str]]:
        """Возвращает все связанные нормы с типами связей"""
        related = []
        for target, rel in self.edges.get(norm_id, []):
            if relation_types is None or rel in relation_types:
                related.append((target, rel))
        for source, rel in self.reverse_edges.get(norm_id, []):
            if relation_types is None or rel in relation_types:
                related.append((source, rel))
        return list(set(related))
    
    def get_related_norm_ids(self, norm_id: str, relation_types: List[str] = None) -> List[str]:
        """Возвращает ID связанных норм"""
        return [n for n, _ in self.get_related_norms(norm_id, relation_types)]
    
    def find_path(self, start: str, target: str, max_depth: int = 3) -> List[List[str]]:
        """Находит пути между нормами (BFS)"""
        from collections import deque
        
        visited = set([start])
        queue = deque([(start, [start])])
        paths = []
        
        while queue and len(paths) < 3:
            node, path = queue.popleft()
            if len(path) > max_depth:
                continue
            
            for neighbor, _ in self.edges.get(node, []):
                if neighbor == target:
                    paths.append(path + [neighbor])
                elif neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return paths
    
    def get_edge_info(self, source: str, target: str) -> Optional[Dict]:
        """Возвращает информацию о ребре"""
        return self.edge_info.get((source, target))
    
    def to_dict(self) -> Dict:
        """Преобразует граф в словарь для сохранения"""
        return {
            "nodes": sorted(self.nodes),
            "edges": {
                source: [(target, rel, self.edge_info.get((source, target), {}).get('description', ''))
                        for target, rel in edges]
                for source, edges in self.edges.items()
            }
        }
    
    def __repr__(self):
        return f"LegalGraph(nodes={len(self.nodes)}, edges={sum(len(v) for v in self.edges.values())})"


# ============================================================
# ФУНКЦИЯ ДЛЯ ПОСТРОЕНИЯ ГРАФА СТАТЬИ 6.1
# ============================================================

def build_graph_6_1() -> LegalGraph:
    """Строит граф для статьи 6.1 115-ФЗ"""
    graph = LegalGraph()
    
    # 1. ИСКЛЮЧЕНИЕ: норма 2 — исключение для нормы 1
    graph.add_edge('2', '1', 'exception_of', 'Норма 2 исключает норму 1 для определенных лиц')
    
    # 2. УТОЧНЕНИЕ: норма 3 уточняет норму 1
    graph.add_edge('3', '1', 'specifies', 'Норма 3 уточняет обязанности из нормы 1')
    graph.add_edge('3.1', '1', 'specifies', 'Подпункт 3.1 уточняет обязанности')
    graph.add_edge('3.2', '1', 'specifies', 'Подпункт 3.2 уточняет обязанности')
    
    # 3. КОРРЕЛЯЦИЯ: норма 4 и норма 5 связаны
    graph.add_edge('4', '5', 'relates_to', 'Норма 4 (право) и норма 5 (обязанность) связаны')
    graph.add_edge('5', '4', 'relates_to', 'Норма 5 (обязанность) и норма 4 (право) связаны')
    
    # 4. ОПРЕДЕЛЕНИЕ: норма 8 определяет термин
    graph.add_edge('8', '1', 'defines', 'Норма 8 определяет бенефициарного владельца')
    graph.add_edge('8', '3', 'defines', 'Норма 8 определяет бенефициарного владельца')
    graph.add_edge('8', '6', 'defines', 'Норма 8 определяет бенефициарного владельца')
    
    # 5. РАСПРОСТРАНЕНИЕ: норма 7.1 распространяется на нормы 1-7
    for n in ['1', '2', '3', '4', '5', '6', '7']:
        graph.add_edge('7.1', n, 'extends_to', f'Норма 7.1 распространяется на норму {n}')
    
    # 6. РАСКРЫТИЕ: норма 7 связана с нормой 1
    graph.add_edge('7', '1', 'relates_to', 'Норма 7 о раскрытии связана с нормой 1')
    
    # 7. ЗАПРОС ОРГАНОВ: норма 6 связана с предоставлением информации
    graph.add_edge('6', '5', 'relates_to', 'Норма 6 связана с предоставлением информации')
    
    # 8. СВЯЗЬ МЕЖДУ 3.1 И 3.2
    graph.add_edge('3.1', '3.2', 'relates_to', 'Оба подпункта в пункте 3')
    graph.add_edge('3.2', '3.1', 'relates_to', 'Оба подпункта в пункте 3')
    
    return graph