from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
import random
import json
import os
from collections import deque, defaultdict


@dataclass
class Character:
    name: str
    image_path: str

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Character name cannot be empty")
        if not self.image_path.strip():
            raise ValueError("Character image path cannot be empty")


@dataclass
class RankingEntry:
    place: int
    character_name: str
    rating: float
    wins: int = 0
    comparisons: int = 0

    def __str__(self) -> str:
        return f"{self.place}. {self.character_name} — {self.rating:.0f} очков ({self.wins} побед из {self.comparisons})"


class SimpleTransitiveSession:
    """
    Оптимизированная сессия попарных сравнений с инкрементальным транзитивным замыканием.
    """

    def __init__(
        self,
        characters_count: int,
        max_comparisons: int = None,
        new_characters_only: bool = False,
        new_character_indices: Optional[List[int]] = None,
    ):
        self.characters_count = characters_count
        self.max_comparisons = max_comparisons  # None — без ограничения

        # Множество всех известных отношений (включая транзитивные): (winner, loser)
        self.wins: Set[Tuple[int, int]] = set()

        # Только прямые сравнения пользователя: key=(min(a,b), max(a,b)), value=winner
        self.results: Dict[Tuple[int, int], int] = {}

        # Адж. списки по текущему замыканию
        self.adj_fwd: Dict[int, Set[int]] = defaultdict(set)   # winner -> losers
        self.adj_rev: Dict[int, Set[int]] = defaultdict(set)   # loser  -> winners

        # Инкрементальные счётчики
        self.win_counts: Dict[int, int] = {i: 0 for i in range(self.characters_count)}
        self.comp_counts: Dict[int, int] = {i: 0 for i in range(self.characters_count)}

        self.comparisons_made = 0

        # Режим «только новые»
        self.new_characters_only = new_characters_only
        self.new_character_indices = set(new_character_indices or [])

        # История для undo: список (pair(min, max), winner)
        self.choice_history: List[Tuple[Tuple[int, int], int]] = []

        # Кэш текущей пары
        self._current_pair: Optional[Tuple[int, int]] = None

        # Все ещё неизвестные пары (min, max)
        self._unknown_pairs: Set[Tuple[int, int]] = set()
        if self.new_characters_only and self.new_character_indices:
            for a in self.new_character_indices:
                for b in range(self.characters_count):
                    if a == b:
                        continue
                    mn, mx = (a, b) if a < b else (b, a)
                    self._unknown_pairs.add((mn, mx))
        else:
            for a in range(self.characters_count):
                for b in range(a + 1, self.characters_count):
                    self._unknown_pairs.add((a, b))

        # Обучение на истории
        self.learned_preferences = self._load_learned_preferences()

    @property
    def is_completed(self) -> bool:
        if self.max_comparisons is not None and self.comparisons_made >= self.max_comparisons:
            return True
        # Проверяем, есть ли вообще неизвестные пары
        return len(self._unknown_pairs) == 0

    @property
    def total_pairs(self) -> int:
        if self.max_comparisons:
            return self.max_comparisons
        # В режиме only-new — верхняя оценка по сформированному набору
        return len(self._unknown_pairs) if self.new_characters_only else (self.characters_count * (self.characters_count - 1)) // 2

    @classmethod
    def create_new(cls, characters_count: int, max_comparisons: int = None):
        return cls(characters_count, max_comparisons)

    @classmethod
    def create_new_characters_session(cls, characters_count: int, new_character_indices: List[int], max_comparisons: int = None):
        return cls(characters_count, max_comparisons, new_characters_only=True, new_character_indices=new_character_indices)

    def get_current_pair(self) -> Optional[Tuple[int, int]]:
        if self.is_completed:
            self._current_pair = None
            return None
        if self._current_pair is None:
            self._current_pair = self._select_next_pair()
        return self._current_pair

    def record_choice(self, pair: Tuple[int, int], winner: int) -> None:
        if pair is None:
            return
        a, b = pair
        if winner not in pair:
            raise ValueError("winner must be one of pair")

        mn, mx = (a, b) if a < b else (b, a)
        # Если уже есть прямой результат по этой паре — игнор
        if (mn, mx) in self.results:
            self._current_pair = None
            return

        loser = b if winner == a else a

        # Если отношение уже известно транзитивно – тоже игнор
        if (winner, loser) in self.wins:
            # Но зафиксируем прямое сравнение в results, чтобы считать comp_counts честно
            self.results[(mn, mx)] = winner
            self.comparisons_made += 1
            self.comp_counts[a] += 1
            self.comp_counts[b] += 1
            # История для undo
            self.choice_history.append(((mn, mx), winner))
            # Обучение
            self.learn_from_choice((mn, mx), winner)
            # Удалим пару из unknown, если там осталась
            self._unknown_pairs.discard((mn, mx))
            self._current_pair = None
            return

        # Прежде чем добавлять, проверим, не приведёт ли к циклу (то есть есть ли путь loser -> winner)
        if self._reachable(loser, winner):
            # Конфликтная информация: создаст цикл. Можно игнорировать или отказаться с ошибкой.
            # Здесь — игнорируем добавление, но фиксируем прямое сравнение.
            self.results[(mn, mx)] = winner
            self.comparisons_made += 1
            self.comp_counts[a] += 1
            self.comp_counts[b] += 1
            self.choice_history.append(((mn, mx), winner))
            self.learn_from_choice((mn, mx), winner)
            self._unknown_pairs.discard((mn, mx))
            self._current_pair = None
            return

        # Записываем прямое сравнение
        self.results[(mn, mx)] = winner
        self.comparisons_made += 1
        self.comp_counts[a] += 1
        self.comp_counts[b] += 1
        self.choice_history.append(((mn, mx), winner))
        self.learn_from_choice((mn, mx), winner)

        # Добавляем новое отношение и все транзитивные следствия: A in Anc(winner), B in Desc(loser)
        self._add_relation_with_closure(winner, loser)

        # Текущая пара больше не актуальна
        self._current_pair = None

    def undo_last_choice(self) -> bool:
        if not self.choice_history:
            return False

        # Удаляем последний прямой результат
        (mn, mx), winner = self.choice_history.pop()
        a, b = mn, mx
        loser = b if winner == a else a

        # Снимем прямую запись
        if (mn, mx) in self.results:
            del self.results[(mn, mx)]
        # Обновим комп-счётчики и сравнений
        self.comparisons_made -= 1
        self.comp_counts[a] -= 1
        self.comp_counts[b] -= 1

        # Полный пересчёт транзитивного замыкания из оставшихся прямых результатов
        self._rebuild_from_direct()

        # Вернём эту пару назад в unknown, если она не стала известной транзитивно
        if (a, b) not in self.wins and (b, a) not in self.wins:
            self._unknown_pairs.add((a, b))

        # Сбрасываем кэш текущей пары
        self._current_pair = None
        return True

    def peek_last_pair(self) -> Optional[Tuple[int, int]]:
        if not self.choice_history:
            return None
        (mn, mx), _ = self.choice_history[-1]
        return (mn, mx)

    def _rebuild_from_direct(self) -> None:
        # Полная очистка графа/замыкания
        self.wins.clear()
        self.adj_fwd = defaultdict(set)
        self.adj_rev = defaultdict(set)
        for i in range(self.characters_count):
            self.win_counts[i] = 0

        # Снова добавим все прямые рёбра и их транзитивные следствия
        for (mn, mx), winner in self.results.items():
            a, b = mn, mx
            loser = b if winner == a else a
            # Защита от циклов: если конфликт — пропускаем (или можно логировать)
            if self._reachable(loser, winner):
                continue
            self._add_relation_with_closure(winner, loser)

        # Обновим unknown_pairs: убрать все пары, которые теперь известны
        to_remove = []
        for (u, v) in self._unknown_pairs:
            if (u, v) in self.wins or (v, u) in self.wins:
                to_remove.append((u, v))
        for p in to_remove:
            self._unknown_pairs.discard(p)

    def _add_relation_with_closure(self, u: int, v: int) -> None:
        """
        Добавляет отношение u > v и транзитивно: A > B для
        A ∈ Anc(u) ∪ {u}, B ∈ Desc(v) ∪ {v}.
        Предполагается, что до вызова граф был в замыкании.
        """
        # Найдём всех предков u (включая u) и всех потомков v (включая v)
        ancestors = self._collect_ancestors_inclusive(u)
        descendants = self._collect_descendants_inclusive(v)

        # Для каждой пары (a, b) добавим ребро, если его ещё нет
        for a in ancestors:
            for b in descendants:
                if a == b:
                    continue
                if (a, b) in self.wins:
                    continue
                # Добавляем новое ребро в замыкание
                self.wins.add((a, b))
                self.adj_fwd[a].add(b)
                self.adj_rev[b].add(a)
                # Инкремент побед
                self.win_counts[a] += 1
                # Пара становится известной — убрать из unknown
                mn, mx = (a, b) if a < b else (b, a)
                self._unknown_pairs.discard((mn, mx))

    def _collect_ancestors_inclusive(self, x: int) -> Set[int]:
        # Все, кто побеждает x (и их предки), плюс сам x
        res = {x}
        q = deque([x])
        while q:
            cur = q.popleft()
            for p in self.adj_rev[cur]:
                if p not in res:
                    res.add(p)
                    q.append(p)
        return res

    def _collect_descendants_inclusive(self, x: int) -> Set[int]:
        # Все, кого побеждает x (и их потомки), плюс сам x
        res = {x}
        q = deque([x])
        while q:
            cur = q.popleft()
            for ch in self.adj_fwd[cur]:
                if ch not in res:
                    res.add(ch)
                    q.append(ch)
        return res

    def _reachable(self, src: int, dst: int) -> bool:
        if src == dst:
            return True
        # Быстрая проверка через текущий граф замыкания
        # Если уже есть путь src -> dst, то (src, dst) в wins
        return (src, dst) in self.wins

    def _load_learned_preferences(self) -> Dict[Tuple[int, int], float]:
        """Загружает изученные предпочтения с обработкой ошибок."""
        try:
            if os.path.exists("learned_preferences.json"):
                with open("learned_preferences.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    result = {}
                    for k, v in data.items():
                        try:
                            key = tuple(map(int, k.split(',')))
                            if len(key) == 2 and all(0 <= x < self.characters_count for x in key):
                                result[key] = float(v)
                        except (ValueError, TypeError):
                            continue  # Пропускаем некорректные записи
                    return result
        except (json.JSONDecodeError, IOError) as e:
            # Логируем ошибку, но не падаем
            pass
        return {}

    def _save_learned_preferences(self) -> None:
        """Сохраняет изученные предпочтения с обработкой ошибок."""
        try:
            data = {f"{k[0]},{k[1]}": v for k, v in self.learned_preferences.items()}
            with open("learned_preferences.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (IOError, OSError):
            # Не критично, просто пропускаем
            pass

    def learn_from_choice(self, pair: Tuple[int, int], winner: int) -> None:
        """Обучается на основе выбора пользователя с валидацией."""
        if pair is None or len(pair) != 2:
            return
        
        a, b = pair
        if not (0 <= a < self.characters_count and 0 <= b < self.characters_count):
            return
        
        if winner not in pair:
            return
            
        loser = b if winner == a else a
        key_ab = (a, b)
        key_ba = (b, a)

        # Инициализация нейтральными значениями
        if key_ab not in self.learned_preferences:
            self.learned_preferences[key_ab] = 0.5
        if key_ba not in self.learned_preferences:
            self.learned_preferences[key_ba] = 0.5

        # Обновляем предпочтения с ограничениями
        learning_rate = 0.1
        if winner == a:
            self.learned_preferences[key_ab] = min(1.0, self.learned_preferences[key_ab] + learning_rate)
            self.learned_preferences[key_ba] = max(0.0, self.learned_preferences[key_ba] - learning_rate)
        else:
            self.learned_preferences[key_ba] = min(1.0, self.learned_preferences[key_ba] + learning_rate)
            self.learned_preferences[key_ab] = max(0.0, self.learned_preferences[key_ab] - learning_rate)

    def get_learned_preference(self, a: int, b: int) -> float:
        """Возвращает изученное предпочтение с валидацией."""
        if not (0 <= a < self.characters_count and 0 <= b < self.characters_count):
            return 0.5
        if a == b:
            return 0.5
        return self.learned_preferences.get((a, b), 0.5)

    def _select_next_pair(self) -> Optional[Tuple[int, int]]:
        if not self._unknown_pairs:
            return None

        # Ранние шаги — случайная пара
        if self.comparisons_made < 10:
            return random.choice(tuple(self._unknown_pairs))

        # Попробуем «продвигать» новых героев против середняков после нескольких сравнений
        if self.new_characters_only:
            # В режиме only-new набор уже ограничен; просто применим эвристику ниже
            pass
        else:
            # Найдём «новых» (ещё без сравнений)
            new_chars = [i for i in range(self.characters_count) if self.comp_counts[i] == 0]
            if new_chars and self.comparisons_made >= 5:
                new_char = random.choice(new_chars)
                experienced = [i for i in range(self.characters_count) if self.comp_counts[i] > 0 and i != new_char]
                if experienced:
                    experienced.sort(key=lambda x: self.win_counts[x])
                    if len(experienced) >= 3:
                        middle_start = len(experienced) // 3
                        middle_end = 2 * len(experienced) // 3
                        middle = experienced[middle_start:middle_end] or experienced
                    else:
                        middle = experienced
                    opponent = random.choice(middle)
                    mn, mx = (new_char, opponent) if new_char < opponent else (opponent, new_char)
                    if (mn, mx) in self._unknown_pairs:
                        return (mn, mx)

        # Эвристика на подвыборке кандидатов (ускорение)
        candidates = self._sample_unknown(200)

        if not candidates:
            return random.choice(tuple(self._unknown_pairs))

        scored = []
        for a, b in candidates:
            win_diff = abs(self.win_counts[a] - self.win_counts[b])
            comp_sum = self.comp_counts[a] + self.comp_counts[b]
            learned_pref = self.get_learned_preference(a, b)
            uncertainty = abs(learned_pref - 0.5)

            # Чем меньше score — тем лучше
            if comp_sum == 0:
                score = 1000 + win_diff - uncertainty * 100
            elif comp_sum < 3:
                score = 500 + win_diff - uncertainty * 50
            else:
                score = win_diff - uncertainty * 200 + max(0, 5 - abs(comp_sum - 6))  # слегка тянем к «среднему» опыту
            scored.append((score, a, b))

        scored.sort()
        top_count = max(1, len(scored) // 3)
        _, a, b = random.choice(scored[:top_count])
        return (a, b)

    def _sample_unknown(self, k: int) -> List[Tuple[int, int]]:
        # Быстрый сэмпл без преобразования всего set в список
        if not self._unknown_pairs:
            return []
        if len(self._unknown_pairs) <= k:
            return list(self._unknown_pairs)
        # Сэмплируем через tuple (эффективнее для random.choice)
        tup = tuple(self._unknown_pairs)
        return [tup[random.randrange(len(tup))] for _ in range(k)]

    def get_statistics(self) -> Dict:
        denom = self.total_pairs if self.total_pairs else 1
        return {
            "comparisons_made": self.comparisons_made,
            "max_comparisons": self.max_comparisons,
            "total_relations": len(self.wins),
            "completion_percentage": min(100.0, (self.comparisons_made / denom) * 100.0),
        }

    def calculate_scores(self) -> List[Tuple[float, int]]:
        # Рейтинг по числу побед (на замыкании)
        return sorted([(self.win_counts[idx], idx) for idx in range(self.characters_count)], reverse=True)

    def save_learning(self) -> None:
        self._save_learned_preferences()