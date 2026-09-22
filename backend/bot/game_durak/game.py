"""
Игровая логика «Дурака» (партии, ходы, правила).
"""
import random
import uuid
from typing import Optional

from .cards import Card, Deck, SUITS, RANKS, RANK_ORDER


class DurakGame:
    """
    Состояние одной партии «Дурака».

    players_count: 2..6
    bot_player: если True — второй игрок управляется ботом.
    """

    def __init__(self, player_ids: list[int], bot_indices: Optional[list[int]] = None, stake: int = 0):
        if not (2 <= len(player_ids) <= 6):
            raise ValueError("Нужно от 2 до 6 игроков")

        self.game_id = str(uuid.uuid4())[:8]
        self.player_ids = player_ids
        self.bot_indices = set(bot_indices or [])
        self.stake = max(0, int(stake))
        self.total_pot = self.stake * len(player_ids)

        deck = Deck()
        self.trump_suit: str = deck.trump_card.suit  # type: ignore
        self.trump_card: Optional[dict] = deck.trump_card.to_dict() if deck.trump_card else None

        # Раздача по 6 карт
        self.hands: dict[int, list[dict]] = {}
        for pid in player_ids:
            dealt = deck.deal(6)
            self.hands[pid] = [c.to_dict() for c in dealt]

        self.deck: list[dict] = [c.to_dict() for c in deck._cards]  # остаток колоды

        # Стол: список {"attack": card_dict, "defend": card_dict | null}
        self.table: list[dict] = []

        # Определяем, кто первым ходит — у кого наименьший козырь
        self.current_attacker: int = self._find_first_attacker()
        self.current_defender: int = self._next_player(self.current_attacker)

        # Фазы: "attack", "defend", "done"
        self.phase: str = "attack"
        self.winner: Optional[int] = None  # None пока игра идёт
        self.loser: Optional[int] = None
        self.beaten: list[dict] = []  # сыгранные карты (отбой)
        self.finished_order: list[int] = []  # порядок выхода игроков (без карт при пустой колоде)

    # ------------------------------------------------------------------
    # Вспомогательные
    # ------------------------------------------------------------------

    def _find_first_attacker(self) -> int:
        best_pid = self.player_ids[0]
        best_rank = None
        for pid in self.player_ids:
            trump_cards = [Card.from_dict(c) for c in self.hands[pid] if c["suit"] == self.trump_suit]
            if trump_cards:
                min_card = min(trump_cards, key=lambda c: RANK_ORDER[c.rank])
                if best_rank is None or RANK_ORDER[min_card.rank] < RANK_ORDER[best_rank]:
                    best_rank = min_card.rank
                    best_pid = pid
        return best_pid

    def _next_player(self, pid: int) -> int:
        idx = self.player_ids.index(pid)
        # Пропускаем вышедших игроков (пустая рука + пустая колода)
        for _ in range(len(self.player_ids) - 1):
            idx = (idx + 1) % len(self.player_ids)
            nxt = self.player_ids[idx]
            if self.hands[nxt] or self.deck:
                return nxt
        return self.player_ids[(self.player_ids.index(pid) + 1) % len(self.player_ids)]

    def _refill_hands(self) -> None:
        """Дотянуть карты до 6 после каждого хода (сначала атакующий)."""
        order = [self.current_attacker] + [
            p for p in self.player_ids if p != self.current_attacker and p != self.current_defender
        ] + [self.current_defender]

        for pid in order:
            while self.deck and len(self.hands[pid]) < 6:
                self.hands[pid].append(self.deck.pop(0))

    def _update_finished_players(self) -> None:
        """Зафиксировать порядок выхода игроков из игры (когда колода пуста)."""
        if self.deck:
            return
        for pid in self.player_ids:
            if not self.hands[pid] and pid not in self.finished_order:
                self.finished_order.append(pid)

    def _check_game_over(self) -> bool:
        """Проверить, закончилась ли игра."""
        if self.deck:
            return False
        self._update_finished_players()
        players_with_cards = [p for p in self.player_ids if self.hands[p]]
        if len(players_with_cards) <= 1:
            if len(players_with_cards) == 1:
                self.loser = players_with_cards[0]
                self.winner = self.finished_order[0] if self.finished_order else None
            else:
                # Все сбросили карты одновременно -> ничья
                self.loser = None
                self.winner = None
            self.phase = "done"
            return True
        return False

    # ------------------------------------------------------------------
    # Игровые действия
    # ------------------------------------------------------------------

    def attack(self, attacker_id: int, card_dict: dict) -> dict:
        """Атака картой."""
        if self.phase != "attack":
            return {"ok": False, "error": "Сейчас не фаза атаки"}
        if attacker_id != self.current_attacker:
            return {"ok": False, "error": "Не ваш ход атаковать"}

        card = Card.from_dict(card_dict)

        # Проверка: карта есть в руке
        if card_dict not in self.hands[attacker_id]:
            return {"ok": False, "error": "Карты нет в руке"}

        # Проверка: первая карта стола — любая; следующие — только того же ранга
        if self.table:
            ranks_on_table = set()
            for slot in self.table:
                ranks_on_table.add(slot["attack"]["rank"])
                if slot.get("defend"):
                    ranks_on_table.add(slot["defend"]["rank"])
            if card.rank not in ranks_on_table:
                return {"ok": False, "error": "Можно подкидывать только карты тех же рангов"}

        # Ограничение: не больше 6 карт на столе
        if len(self.table) >= 6:
            return {"ok": False, "error": "Больше карт подкидывать нельзя (максимум 6 на столе)"}

        # Защитник должен иметь карты в руке для отбоя
        defender_hand = self.hands[self.current_defender]
        if not defender_hand:
            return {"ok": False, "error": "У защитника не осталось карт"}

        # Число неотбитых карт на столе не должно превышать число карт в руке защитника
        unclosed = sum(1 for slot in self.table if slot.get("defend") is None)
        if unclosed >= len(defender_hand):
            return {"ok": False, "error": "У защитника недостаточно карт для отбоя"}

        self.hands[attacker_id].remove(card_dict)
        self.table.append({"attack": card_dict, "defend": None})
        self.phase = "defend"
        return {"ok": True}

    def defend(self, defender_id: int, attack_card_dict: dict, defend_card_dict: dict) -> dict:
        """Защита: бить карту attack_card_dict картой defend_card_dict."""
        if self.phase != "defend":
            return {"ok": False, "error": "Сейчас не фаза защиты"}
        if defender_id != self.current_defender:
            return {"ok": False, "error": "Не ваш ход защищаться"}

        # Найти незакрытый слот
        slot = None
        for s in self.table:
            if s["attack"] == attack_card_dict and s["defend"] is None:
                slot = s
                break
        if slot is None:
            return {"ok": False, "error": "Карта для отбоя не найдена на столе"}

        if defend_card_dict not in self.hands[defender_id]:
            return {"ok": False, "error": "Карты нет в руке"}

        attack_card = Card.from_dict(attack_card_dict)
        defend_card = Card.from_dict(defend_card_dict)

        if not defend_card.beats(attack_card, self.trump_suit):
            return {"ok": False, "error": "Этой картой нельзя отбить"}

        self.hands[defender_id].remove(defend_card_dict)
        slot["defend"] = defend_card_dict

        # Если все карты на столе отбиты → атакующий может подкинуть или завершить ход
        all_closed = all(s["defend"] is not None for s in self.table)
        if all_closed:
            # Если колода пуста и у одного из участников закончились карты — авто-отбой
            if not self.deck and (not self.hands[self.current_attacker] or not self.hands[self.current_defender]):
                return self.pass_attack(self.current_attacker)
            # Если на столе уже 6 карт или у защитника не осталось карт — авто-отбой
            if len(self.table) >= 6 or not self.hands[self.current_defender]:
                return self.pass_attack(self.current_attacker)
            self.phase = "attack"
        return {"ok": True}

    def take(self, defender_id: int) -> dict:
        """Защитник берёт все карты со стола."""
        if defender_id != self.current_defender:
            return {"ok": False, "error": "Не ваш ход"}
        if not self.table:
            return {"ok": False, "error": "Стол пуст"}

        # Взять все карты стола в руку
        for slot in self.table:
            self.hands[defender_id].append(slot["attack"])
            if slot["defend"]:
                self.hands[defender_id].append(slot["defend"])
        self.table = []

        # Ход переходит к следующему после защитника
        new_attacker = self._next_player(self.current_defender)
        self.current_defender = self._next_player(new_attacker)
        self.current_attacker = new_attacker

        self._refill_hands()
        if self._check_game_over():
            return {"ok": True}
        self.phase = "attack"
        return {"ok": True}

    def pass_attack(self, attacker_id: int) -> dict:
        """Атакующий завершает ход (больше не подкидывает)."""
        if attacker_id != self.current_attacker:
            return {"ok": False, "error": "Не ваш ход"}

        # Проверка: все карты на столе отбиты
        open_slots = [s for s in self.table if s["defend"] is None]
        if open_slots:
            return {"ok": False, "error": "Не все карты отбиты — сначала подождите ответа защитника"}

        # Отбой — снять карты со стола
        for slot in self.table:
            self.beaten.append(slot["attack"])
            if slot["defend"]:
                self.beaten.append(slot["defend"])
        self.table = []

        # Ход переходит к защитнику
        new_attacker = self.current_defender
        self.current_defender = self._next_player(new_attacker)
        self.current_attacker = new_attacker

        self._refill_hands()
        if self._check_game_over():
            return {"ok": True}
        self.phase = "attack"
        return {"ok": True}

    # ------------------------------------------------------------------
    # Ход бота
    # ------------------------------------------------------------------

    def bot_move(self) -> Optional[dict]:
        """
        Выполнить ход за бота. Возвращает описание действия или None.
        """
        if self.phase == "done":
            return None

        if self.phase == "attack" and self.current_attacker in self.bot_indices:
            hand = self.hands[self.current_attacker]
            if not hand:
                return self.pass_attack(self.current_attacker)

            if self.table:
                ranks_on_table = set()
                for slot in self.table:
                    ranks_on_table.add(slot["attack"]["rank"])
                    if slot.get("defend"):
                        ranks_on_table.add(slot["defend"]["rank"])
                candidates = [c for c in hand if c["rank"] in ranks_on_table]
            else:
                candidates = list(hand)

            if not candidates:
                return self.pass_attack(self.current_attacker)

            non_trump = [c for c in candidates if c["suit"] != self.trump_suit]
            result = self.attack(self.current_attacker, choice)
            if not result.get("ok"):
                return self.pass_attack(self.current_attacker)
            return {"action": "attack", "card": choice, "result": result}

        elif self.phase == "defend" and self.current_defender in self.bot_indices:
            hand = self.hands[self.current_defender]
            open_slots = [s for s in self.table if s["defend"] is None]
            if not open_slots:
                return self.pass_attack(self.current_attacker)

            slot = open_slots[0]
            atk_card = Card.from_dict(slot["attack"])

            best_def = None
            best_def_dict = None
            for cd in hand:
                c = Card.from_dict(cd)
                if c.beats(atk_card, self.trump_suit):
                    if best_def is None:
                        best_def = c
                        best_def_dict = cd
                    else:
                        if best_def.suit == self.trump_suit and c.suit != self.trump_suit:
                            best_def = c
                            best_def_dict = cd
                        elif best_def.suit == c.suit and RANK_ORDER[c.rank] < RANK_ORDER[best_def.rank]:
                            best_def = c
                            best_def_dict = cd

            if best_def_dict:
                result = self.defend(self.current_defender, slot["attack"], best_def_dict)
                return {"action": "defend", "card": best_def_dict, "result": result}
            else:
                result = self.take(self.current_defender)
                return {"action": "take", "result": result}

        return None

    # ------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------

    def to_state(self, for_player_id: Optional[int] = None) -> dict:
        """
        Сериализовать состояние игры.
        Если for_player_id указан — скрыть чужие карты.
        """
        hands_view: dict = {}
        for pid in self.player_ids:
            if for_player_id is None or pid == for_player_id or pid in self.bot_indices:
                hands_view[str(pid)] = self.hands[pid]
            else:
                hands_view[str(pid)] = len(self.hands[pid])  # type: ignore

        return {
            "game_id": self.game_id,
            "trump_suit": self.trump_suit,
            "trump_card": self.trump_card,
            "deck_count": len(self.deck),
            "hands": hands_view,
            "table": self.table,
            "current_attacker": self.current_attacker,
            "current_defender": self.current_defender,
            "phase": self.phase,
            "winner": self.winner,
            "loser": self.loser,
            "stake": self.stake,
            "total_pot": self.total_pot,
            "player_ids": self.player_ids,
            "bot_indices": list(self.bot_indices),
            "finished_order": list(self.finished_order),
        }
