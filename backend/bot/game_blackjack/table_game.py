"""
Движок многопользовательского стола «Блэкджек» (2–4 игрока против общего Дилера).
"""
import uuid
from typing import List, Dict, Any, Optional
from backend.bot.game_blackjack.cards import Card, Deck, calculate_hand_value


class TablePlayer:
    def __init__(self, user_id: int, name: str):
        self.user_id: int = user_id
        self.name: str = name
        self.stake: int = 0
        self.cards: List[Card] = []
        self.status: str = "waiting"  # "waiting", "bet_placed", "waiting_turn", "acting", "stand", "double", "bust", "blackjack", "win", "dealer_win", "push"
        self.payout: int = 0
        self.net_profit: int = 0

    def reset_round(self) -> None:
        self.cards = []
        self.status = "waiting"
        self.payout = 0
        self.net_profit = 0

    def to_dict(self) -> Dict[str, Any]:
        score, is_soft = calculate_hand_value(self.cards)
        return {
            "user_id": self.user_id,
            "name": self.name,
            "stake": self.stake,
            "cards": [c.to_dict() for c in self.cards],
            "score": score,
            "is_soft": is_soft,
            "status": self.status,
            "payout": self.payout,
            "net_profit": self.net_profit,
            "can_double": self.status == "acting" and len(self.cards) == 2,
        }


class BlackjackTableGame:
    """
    Класс общего стола казино в Блэкджек на 2–4 места.
    """

    def __init__(self, max_players: int = 4, min_stake: int = 10):
        self.table_id: str = str(uuid.uuid4())[:8]
        self.max_players: int = max(2, min(4, max_players))
        self.min_stake: int = max(1, min_stake)
        self.players: List[TablePlayer] = []
        self.dealer_cards: List[Card] = []
        self.deck: Deck = Deck(shuffle=True)
        self.phase: str = "lobby"  # "lobby", "betting", "player_turns", "dealer_turn", "settled"
        self.active_player_idx: int = -1

    def add_player(self, user_id: int, name: str) -> bool:
        if len(self.players) >= self.max_players:
            return False
        if any(p.user_id == user_id for p in self.players):
            return True
        self.players.append(TablePlayer(user_id=user_id, name=name))
        return True

    def remove_player(self, user_id: int) -> bool:
        idx = next((i for i, p in enumerate(self.players) if p.user_id == user_id), -1)
        if idx == -1:
            return False
        self.players.pop(idx)
        if self.phase == "player_turns":
            if self.active_player_idx >= len(self.players):
                self._advance_turn()
            elif self.active_player_idx == idx:
                self._advance_turn()
        if not self.players:
            self.phase = "lobby"
        return True

    def place_bet(self, user_id: int, stake: int) -> Dict[str, Any]:
        player = next((p for p in self.players if p.user_id == user_id), None)
        if not player:
            return {"ok": False, "error": "Игрок не за столом"}
        if self.phase not in ("lobby", "betting", "settled"):
            return {"ok": False, "error": "Ставки сейчас не принимаются"}

        if stake < self.min_stake:
            return {"ok": False, "error": f"Минимальная ставка {self.min_stake} 🪙"}

        player.stake = stake
        player.status = "bet_placed"
        self.phase = "betting"

        all_ready = len(self.players) >= 1 and all(p.status == "bet_placed" for p in self.players)
        return {"ok": True, "all_ready": all_ready}

    def start_deal(self) -> Dict[str, Any]:
        ready_players = [p for p in self.players if p.status == "bet_placed"]
        if not ready_players:
            return {"ok": False, "error": "Ни один игрок не сделал ставку"}

        if self.deck.remaining < 25:
            self.deck = Deck(shuffle=True)

        self.dealer_cards = []
        for p in self.players:
            if p.status == "bet_placed":
                p.cards = [self.deck.draw(), self.deck.draw()]
                p_score, _ = calculate_hand_value(p.cards)
                if p_score == 21:
                    p.status = "blackjack"
                else:
                    p.status = "waiting_turn"
            else:
                p.cards = []

        self.dealer_cards = [self.deck.draw(), self.deck.draw()]

        self.phase = "player_turns"
        self.active_player_idx = -1
        self._advance_turn()
        return {"ok": True}

    def _advance_turn(self) -> None:
        """Переход хода к следующему игроку или к дилеру."""
        next_idx = self.active_player_idx + 1
        while next_idx < len(self.players):
            p = self.players[next_idx]
            if p.status == "waiting_turn":
                self.active_player_idx = next_idx
                p.status = "acting"
                return
            next_idx += 1

        self._dealer_turn()

    def get_active_player(self) -> Optional[TablePlayer]:
        if 0 <= self.active_player_idx < len(self.players):
            return self.players[self.active_player_idx]
        return None

    def player_hit(self, user_id: int) -> Dict[str, Any]:
        if self.phase != "player_turns":
            return {"ok": False, "error": "Сейчас не фаза ходов"}
        player = self.get_active_player()
        if not player or player.user_id != user_id:
            return {"ok": False, "error": "Не ваш ход"}

        card = self.deck.draw()
        player.cards.append(card)
        score, _ = calculate_hand_value(player.cards)

        if score > 21:
            player.status = "bust"
            self._advance_turn()
        elif score == 21:
            player.status = "stand"
            self._advance_turn()

        return {"ok": True}

    def player_stand(self, user_id: int) -> Dict[str, Any]:
        if self.phase != "player_turns":
            return {"ok": False, "error": "Сейчас не фаза ходов"}
        player = self.get_active_player()
        if not player or player.user_id != user_id:
            return {"ok": False, "error": "Не ваш ход"}

        player.status = "stand"
        self._advance_turn()
        return {"ok": True}

    def player_double(self, user_id: int) -> Dict[str, Any]:
        if self.phase != "player_turns":
            return {"ok": False, "error": "Сейчас не фаза ходов"}
        player = self.get_active_player()
        if not player or player.user_id != user_id:
            return {"ok": False, "error": "Не ваш ход"}
        if len(player.cards) != 2:
            return {"ok": False, "error": "Удвоить можно только с 2 карт"}

        player.stake *= 2
        card = self.deck.draw()
        player.cards.append(card)
        score, _ = calculate_hand_value(player.cards)

        if score > 21:
            player.status = "bust"
        else:
            player.status = "double"
        self._advance_turn()
        return {"ok": True}

    def _dealer_turn(self) -> None:
        """Розыгрыш карт дилера по правилам казино (добор до 17+)."""
        self.phase = "dealer_turn"
        self.active_player_idx = -1

        non_busted = [p for p in self.players if p.status in ("stand", "double", "blackjack")]
        if non_busted:
            while True:
                d_score, _ = calculate_hand_value(self.dealer_cards)
                if d_score < 17:
                    self.dealer_cards.append(self.deck.draw())
                else:
                    break

        self.settle_results()

    def settle_results(self) -> None:
        """Итоговый расчет выплат для каждого игрока."""
        self.phase = "settled"
        dealer_score, _ = calculate_hand_value(self.dealer_cards)
        dealer_has_bj = len(self.dealer_cards) == 2 and dealer_score == 21

        for p in self.players:
            if not p.cards:
                continue
            p_score, _ = calculate_hand_value(p.cards)

            if p.status == "bust":
                p.payout = 0
                p.net_profit = -p.stake
            elif p.status == "blackjack":
                if dealer_has_bj:
                    p.status = "push"
                    p.payout = p.stake
                    p.net_profit = 0
                else:
                    p.payout = p.stake + int(p.stake * 1.5)
                    p.net_profit = int(p.stake * 1.5)
            else:
                if dealer_score > 21:
                    p.status = "win"
                    p.payout = p.stake * 2
                    p.net_profit = p.stake
                elif p_score > dealer_score:
                    p.status = "win"
                    p.payout = p.stake * 2
                    p.net_profit = p.stake
                elif p_score < dealer_score:
                    p.status = "dealer_win"
                    p.payout = 0
                    p.net_profit = -p.stake
                else:
                    p.status = "push"
                    p.payout = p.stake
                    p.net_profit = 0

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация состояния стола для отправки клиентам."""
        is_hidden = self.phase in ("lobby", "betting", "player_turns")
        dealer_score, dealer_soft = calculate_hand_value(self.dealer_cards)

        if is_hidden and self.dealer_cards:
            dealer_view = [
                self.dealer_cards[0].to_dict(),
                {"suit": "?", "rank": "?", "suit_name": "unknown", "value": 0, "hidden": True}
            ]
            d1_score, d1_soft = calculate_hand_value([self.dealer_cards[0]])
            d_score_view = d1_score
            d_soft_view = d1_soft
        else:
            dealer_view = [c.to_dict() for c in self.dealer_cards]
            d_score_view = dealer_score
            d_soft_view = dealer_soft

        active_uid = self.players[self.active_player_idx].user_id if 0 <= self.active_player_idx < len(self.players) else None

        return {
            "table_id": self.table_id,
            "phase": self.phase,
            "max_players": self.max_players,
            "min_stake": self.min_stake,
            "active_user_id": active_uid,
            "dealer_cards": dealer_view,
            "dealer_score": d_score_view,
            "dealer_is_soft": d_soft_view,
            "players": [p.to_dict() for p in self.players],
        }
