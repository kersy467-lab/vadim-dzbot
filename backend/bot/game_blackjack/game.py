from typing import List, Dict, Any, Optional
from backend.bot.game_blackjack.cards import Card, Deck, calculate_hand_value


class BlackjackGame:
    def __init__(self, stake: int = 0):
        self.deck = Deck(shuffle=True)
        self.player_cards: List[Card] = []
        self.dealer_cards: List[Card] = []
        self.stake: int = max(0, stake)
        self.original_stake: int = self.stake
        self.phase: str = "betting"  # "betting", "player_turn", "done"
        self.status: str = "playing"  # "playing", "player_bust", "dealer_bust", "player_win", "dealer_win", "push", "blackjack"
        self.payout: int = 0

    def deal(self, stake: Optional[int] = None) -> Dict[str, Any]:
        """Раздача начальных двух карт игроку и дилеру."""
        if stake is not None:
            self.stake = max(0, stake)
        if not hasattr(self, "deck") or self.deck is None or getattr(self.deck, "remaining", 0) < 15:
            self.deck = Deck(shuffle=True)
        self.player_cards = [self.deck.draw(), self.deck.draw()]
        self.dealer_cards = [self.deck.draw(), self.deck.draw()]
        self.phase = "player_turn"
        self.status = "playing"
        self.payout = 0

        player_score, _ = calculate_hand_value(self.player_cards)
        dealer_score, _ = calculate_hand_value(self.dealer_cards)

        # Проверка натурального блэкджека (21 с первых двух карт)
        if player_score == 21:
            self.phase = "done"
            if dealer_score == 21:
                self.status = "push"
                self.payout = self.stake  # Возврат ставки
            else:
                self.status = "blackjack"
                # Выплата 3:2: возврат ставки + 1.5x ставки чистой прибыли
                self.payout = self.stake + int(self.stake * 1.5)

        return self.to_dict()

    def hit(self) -> Dict[str, Any]:
        """Игрок берет дополнительную карту."""
        if self.phase != "player_turn":
            return self.to_dict()

        card = self.deck.draw()
        self.player_cards.append(card)

        player_score, _ = calculate_hand_value(self.player_cards)
        if player_score > 21:
            self.phase = "done"
            self.status = "player_bust"
            self.payout = 0
        elif player_score == 21:
            # Автоматическая остановка при 21
            return self.stand()

        return self.to_dict()

    def stand(self) -> Dict[str, Any]:
        """Игрок завершает ход, ход переходит к дилеру."""
        if self.phase != "player_turn":
            return self.to_dict()

        self._dealer_turn()
        return self.to_dict()

    def double_down(self) -> Dict[str, Any]:
        """Удвоение ставки: игрок получает ровно 1 карту и завершает ход."""
        if self.phase != "player_turn" or len(self.player_cards) != 2:
            return self.to_dict()

        self.stake *= 2
        card = self.deck.draw()
        self.player_cards.append(card)

        player_score, _ = calculate_hand_value(self.player_cards)
        if player_score > 21:
            self.phase = "done"
            self.status = "player_bust"
            self.payout = 0
        else:
            self._dealer_turn()

        return self.to_dict()

    def _dealer_turn(self) -> None:
        """Розыгрыш карт дилера по стандартным правилам (добор до 17+)."""
        self.phase = "done"

        # Дилер обязан добирать карты, пока сумма строго меньше 17
        while True:
            d_score, _ = calculate_hand_value(self.dealer_cards)
            if d_score < 17:
                self.dealer_cards.append(self.deck.draw())
            else:
                break

        player_score, _ = calculate_hand_value(self.player_cards)
        dealer_score, _ = calculate_hand_value(self.dealer_cards)

        if dealer_score > 21:
            self.status = "dealer_bust"
            self.payout = self.stake * 2
        elif player_score > dealer_score:
            self.status = "player_win"
            self.payout = self.stake * 2
        elif player_score < dealer_score:
            self.status = "dealer_win"
            self.payout = 0
        else:
            self.status = "push"
            self.payout = self.stake

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация текущего состояния партии для фронтенда и API."""
        player_score, player_is_soft = calculate_hand_value(self.player_cards)

        is_finished = self.phase == "done"
        can_double = self.phase == "player_turn" and len(self.player_cards) == 2

        if is_finished:
            dealer_score, dealer_is_soft = calculate_hand_value(self.dealer_cards)
            dealer_view = [c.to_dict() for c in self.dealer_cards]
        else:
            # До окончания партии вторая карта дилера скрыта
            if self.dealer_cards:
                dealer_view = [
                    self.dealer_cards[0].to_dict(),
                    {"suit": "?", "rank": "?", "suit_name": "unknown", "value": 0, "hidden": True}
                ]
                d1_score, d1_soft = calculate_hand_value([self.dealer_cards[0]])
                dealer_score = d1_score
                dealer_is_soft = d1_soft
            else:
                dealer_view = []
                dealer_score = 0
                dealer_is_soft = False

        net_profit = self.payout - self.stake if is_finished else 0

        return {
            "phase": self.phase,
            "status": self.status,
            "stake": self.stake,
            "original_stake": self.original_stake,
            "can_double": can_double,
            "player_cards": [c.to_dict() for c in self.player_cards],
            "player_score": player_score,
            "player_is_soft": player_is_soft,
            "dealer_cards": dealer_view,
            "dealer_score": dealer_score,
            "dealer_is_soft": dealer_is_soft,
            "payout": self.payout,
            "net_profit": net_profit,
        }
