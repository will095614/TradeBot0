"""Item 5 patch: matching-engine trigger checks + symmetric TP slippage.

Bug (LIMIT / STOP_MARKET): submit_order() filled every order immediately
at its stated price, with no trigger check at all.
- A BUY LIMIT at $2400 filled at once even while the market was $2500.
- A SELL STOP_MARKET at $2400 filled at once even while the market was
  $2500 and the stop had never been touched.
The bracket exits in on_tick() were NOT affected (they already check the
bar high/low before submitting), but the public submit_order() /
execute_order() entry point had no gate, so any direct LIMIT / STOP_MARKET
order filled unconditionally.

Fix:
- Public submit_order() now gates resting orders: MARKET fills at once;
  LIMIT / STOP_MARKET only fill once the market touches their price. An
  untriggered order is parked in broker.pending_orders (NOT a rejection,
  NOT logged in rejection_audit) and re-evaluated on every on_tick()
  against the bar's high/low (BUY LIMIT: low <= limit; SELL LIMIT:
  high >= limit; BUY STOP: high >= stop; SELL STOP: low <= stop).
- The fill path is split out as _execute_fill() (validation + execution +
  bracket registration, no trigger gate). on_tick() bracket exits
  (SL / TP / liquidation / circuit breaker) call it directly because they
  already evaluated their own triggers against the bar high/low; routing
  them through the public gate would wrongly reject a stop whose bar low
  pierced it but whose close recovered above it.
- Pending fills use the tick timestamp (frozen OrderTicket is replaced),
  and re-run RiskGuard validation at fill time.

TP slippage (decision: make TP pay slippage, symmetric with SL):
- Before: TP was a LIMIT fill at the exact target price (zero slippage)
  while the SL leg next to it paid half-spread + depth + volatility
  adverse selection. Every TP win was booked at full value while every
  SL loss was enlarged -- a systematic optimistic bias on exits.
- Now: on_tick() applies compute_execution_slippage (MARKET semantics,
  adverse direction) to the TP trigger price and bakes the adjusted price
  into the LIMIT ticket, so TP fills just under the target for longs
  (just over for shorts) -- whenever slippage is enabled
  (slippage_pct > 0). With slippage_pct = 0 the venue stays exact, per
  the existing convention that 0 means "no slippage anywhere" (the
  MARKET-entry tests pin exact fill prices at slippage 0).
  This is the conservative, symmetric model for a paper arena; it is NOT
  real-exchange resting-limit behaviour, but the venue here has no real
  order book -- both exits are synthetic triggers evaluated on bar
  high/low, so both should pay the same execution cost.
- tests/test_broker_sim.py::test_take_profit_fill_pays_slippage covers
  it with slippage enabled; tests/test_evolution.py keeps its exact
  $2600.00 assertion under slippage 0 (unchanged).

Usage: python fix_item5_patch.py [project_root]
Verifies EVERY replacement anchor appears exactly once before writing anything.
Preserves each file's original newline style (CRLF stays CRLF).
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
assert (ROOT / "src/data/live_engine.py").exists(), f"not a TradeBot0 root: {ROOT}"

# (rel_path, old, new) — old must occur exactly once.
REPLACEMENTS = []
# (rel_path, marker_that_must_not_exist_yet, text_to_append)
APPENDS = []


def rep(rel, old, new):
    REPLACEMENTS.append((rel, old, new))


def app(rel, marker, text):
    APPENDS.append((rel, marker, text))


def _read(path):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")
    if crlf:
        text = text.replace("\r\n", "\n")
    return text, crlf


def _write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------- broker_sim.py: imports
rep("src/arena/broker_sim.py",
    """from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
import time
""",
    """from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
import time
""")

# ---------------------------------------------------------------- broker_sim.py: pending book
rep("src/arena/broker_sim.py",
    """        self.active_stops: Dict[str, OrderTicket] = {}    # portfolio_id -> active stop loss order
        self.active_targets: Dict[str, OrderTicket] = {}  # portfolio_id -> active take profit order
""",
    """        self.active_stops: Dict[str, OrderTicket] = {}    # portfolio_id -> active stop loss order
        self.active_targets: Dict[str, OrderTicket] = {}  # portfolio_id -> active take profit order
        self.pending_orders: Dict[str, OrderTicket] = {}  # order_id -> resting LIMIT / STOP_MARKET awaiting trigger
""")

# ---------------------------------------------------------------- broker_sim.py: split submit_order / _execute_fill
rep("src/arena/broker_sim.py",
    """    def submit_order(self, ticket: OrderTicket) -> Optional[FillEvent]:
        \"\"\"
        Executes an order ticket in paper arena mode without interactive blockage.
        \"\"\"
        portfolio = self.portfolios.get(ticket.portfolio_id)
        if not portfolio:
            raise KeyError(f"Unknown portfolio {ticket.portfolio_id}")

        ref_price = ticket.price if ticket.price is not None else self.current_price
""",
    """    def submit_order(self, ticket: OrderTicket) -> Optional[FillEvent]:
        \"\"\"
        Public order entry: MARKET orders fill immediately; LIMIT and
        STOP_MARKET orders only fill once the market touches their price.

        An untriggered LIMIT / STOP_MARKET order is parked in
        ``pending_orders`` (it is NOT a rejection and is NOT logged in
        ``rejection_audit``) and re-evaluated on every ``on_tick`` against
        the bar's high/low. ``on_tick`` bracket exits (SL / TP / liquidation /
        circuit breaker) already evaluated their own triggers, so they call
        ``_execute_fill`` directly and bypass this gate.
        \"\"\"
        # Resting orders need a real market price to judge the trigger;
        # before the first tick there is nothing to compare against.
        if ticket.price is not None and self.current_price > Decimal("0"):
            if ticket.order_type == OrderType.LIMIT:
                if not self._limit_hit(ticket.side, ticket.price, self.current_price, self.current_price):
                    self.pending_orders[ticket.order_id] = ticket
                    return None
            elif ticket.order_type == OrderType.STOP_MARKET:
                if not self._stop_hit(ticket.side, ticket.price, self.current_price, self.current_price):
                    self.pending_orders[ticket.order_id] = ticket
                    return None
        return self._execute_fill(ticket)

    @staticmethod
    def _limit_hit(side: OrderSide, limit_price: Decimal, low: Decimal, high: Decimal) -> bool:
        \"\"\"True when the bar traded at or through a LIMIT price.\"\"\"
        if side == OrderSide.BUY:
            return low <= limit_price
        return high >= limit_price

    @staticmethod
    def _stop_hit(side: OrderSide, stop_price: Decimal, low: Decimal, high: Decimal) -> bool:
        \"\"\"True when the bar traded at or through a STOP trigger price.\"\"\"
        if side == OrderSide.BUY:
            return high >= stop_price
        return low <= stop_price

    def _execute_fill(self, ticket: OrderTicket) -> Optional[FillEvent]:
        \"\"\"
        Immediate fill path: RiskGuard validation + execution + bracket
        registration. The caller must already have evaluated any trigger
        (public ``submit_order`` for resting orders, ``on_tick`` for
        bracket exits whose trigger was checked against the bar high/low).
        \"\"\"
        portfolio = self.portfolios.get(ticket.portfolio_id)
        if not portfolio:
            raise KeyError(f"Unknown portfolio {ticket.portfolio_id}")

        ref_price = ticket.price if ticket.price is not None else self.current_price
""")

# ---------------------------------------------------------------- broker_sim.py: SL branch bypasses the public gate
rep("src/arena/broker_sim.py",
    """                    stop_fill = self.submit_order(OrderTicket(
""",
    """                    stop_fill = self._execute_fill(OrderTicket(
""")

# ---------------------------------------------------------------- broker_sim.py: TP branch pays slippage + bypasses gate
rep("src/arena/broker_sim.py",
    """                if target_hit:
                    trigger_p = (min(bar_open, target_order.price) if is_short else max(bar_open, target_order.price)) if open_price is not None else target_order.price
                    target_fill = self.submit_order(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=exit_side,
                        order_type=OrderType.LIMIT,
                        qty=p.position_qty,
                        price=trigger_p,
                        reason=ExecutionReason.TAKE_PROFIT,
                        timestamp=ts
                    ))
""",
    """                if target_hit:
                    trigger_p = (min(bar_open, target_order.price) if is_short else max(bar_open, target_order.price)) if open_price is not None else target_order.price
                    # Take-profit pays the same execution slippage as a stop
                    # fill (half-spread + depth + volatility adverse
                    # selection): a LIMIT fill lands exactly on
                    # ticket.price, so the slippage-adjusted price is baked
                    # into the ticket instead of booking the win at the
                    # exact target while the SL leg next to it pays slippage.
                    # Gated on slippage_pct > 0: the venue convention is
                    # that slippage 0 means no slippage anywhere.
                    if self.slippage_pct > Decimal("0"):
                        tp_price = self.compute_execution_slippage(
                            side=exit_side,
                            order_type=OrderType.MARKET,
                            qty=p.position_qty,
                            mid_price=trigger_p,
                            atr=self.current_atr,
                        )
                    else:
                        tp_price = trigger_p
                    target_fill = self._execute_fill(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=exit_side,
                        order_type=OrderType.LIMIT,
                        qty=p.position_qty,
                        price=tp_price,
                        reason=ExecutionReason.TAKE_PROFIT,
                        timestamp=ts
                    ))
""")

# ---------------------------------------------------------------- broker_sim.py: evaluate pending orders each tick
rep("src/arena/broker_sim.py",
    """        # 2. Update end-of-bar valuation & check 15% drawdown circuit breaker
""",
    """        # 1b. Evaluate resting (pending) LIMIT / STOP_MARKET orders against
        # this bar's high/low. A triggered order fills now: LIMIT at its
        # limit price, STOP_MARKET at market with slippage around the stop.
        # Validation runs again at fill time; an order that no longer
        # passes is dropped (rejection is logged by _execute_fill).
        if self.pending_orders:
            for order_id in list(self.pending_orders.keys()):
                ticket = self.pending_orders.get(order_id)
                if ticket is None or ticket.price is None:
                    continue
                if ticket.order_type == OrderType.LIMIT:
                    hit = self._limit_hit(ticket.side, ticket.price, low_price, high_price)
                elif ticket.order_type == OrderType.STOP_MARKET:
                    hit = self._stop_hit(ticket.side, ticket.price, low_price, high_price)
                else:
                    hit = False
                if not hit:
                    continue
                del self.pending_orders[order_id]
                pending_fill = self._execute_fill(replace(ticket, timestamp=ts))
                if pending_fill:
                    fills.append(pending_fill)

        # 2. Update end-of-bar valuation & check 15% drawdown circuit breaker
""")

# ---------------------------------------------------------------- broker_sim.py: liquidation / CB bypass the public gate
rep("src/arena/broker_sim.py",
    """                    liq_fill = self.submit_order(OrderTicket(
""",
    """                    liq_fill = self._execute_fill(OrderTicket(
""")

rep("src/arena/broker_sim.py",
    """                    cb_fill = self.submit_order(OrderTicket(
""",
    """                    cb_fill = self._execute_fill(OrderTicket(
""")

# ---------------------------------------------------------------- tests/test_broker_sim.py: imports
rep("tests/test_broker_sim.py",
    """from src.arena.order import OrderTicket, OrderSide, OrderType
""",
    """from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason, PositionSide
""")

# ---------------------------------------------------------------- tests/test_broker_sim.py: new trigger + TP slippage tests
NEW_TESTS = '''
def test_limit_buy_waits_until_price_reaches_limit():
    """Item 5: a BUY LIMIT must not fill above its limit price."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)

    ticket = OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.LIMIT,
                         qty=Decimal("0.1"), price=Decimal("2400.00"), timestamp=101.0)
    assert broker.submit_order(ticket) is None  # 2500 > 2400: not triggered
    assert p.position_qty == Decimal("0.0000")
    assert ticket.order_id in broker.pending_orders
    assert broker.rejection_audit == []  # parked, not rejected

    # Bar dips to 2440: still above the limit, stays parked.
    fills = broker.on_tick(price=Decimal("2450.00"), high=Decimal("2460.00"),
                           low=Decimal("2440.00"), timestamp=102.0)
    assert fills == []
    assert ticket.order_id in broker.pending_orders

    # Bar touches 2390: limit hit, fills at the limit price (not the low).
    fills = broker.on_tick(price=Decimal("2395.00"), high=Decimal("2405.00"),
                           low=Decimal("2390.00"), timestamp=103.0)
    assert len(fills) == 1
    assert fills[0].price == Decimal("2400.00")
    assert p.position_qty == Decimal("0.1000")
    assert ticket.order_id not in broker.pending_orders


def test_limit_sell_fills_immediately_when_already_marketable():
    """Item 5: a LIMIT already through the market fills at once, at the limit price."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)

    # SELL LIMIT 2400 while market is 2500: already marketable, fills now at 2400.
    ticket = OrderTicket("p1", "ETH/USD", OrderSide.SELL, OrderType.LIMIT,
                         qty=Decimal("0.1"), price=Decimal("2400.00"), timestamp=101.0)
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert fill.price == Decimal("2400.00")
    assert p.position_side == PositionSide.SHORT


def test_stop_market_waits_until_trigger():
    """Item 5: a SELL STOP_MARKET must not fill before the stop is touched."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)

    # Open long 0.5 ETH at 2500 (no bracket attached).
    entry = OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET,
                        qty=Decimal("0.5"), timestamp=100.0)
    assert broker.submit_order(entry) is not None
    assert p.position_qty == Decimal("0.5000")

    # Resting sell-stop at 2400: market is 2500, must park, not fill.
    stop = OrderTicket("p1", "ETH/USD", OrderSide.SELL, OrderType.STOP_MARKET,
                       qty=Decimal("0.5"), price=Decimal("2400.00"), timestamp=101.0)
    assert broker.submit_order(stop) is None
    assert p.position_qty == Decimal("0.5000")
    assert stop.order_id in broker.pending_orders

    # Bar low 2410: stop not touched, still parked.
    fills = broker.on_tick(price=Decimal("2450.00"), high=Decimal("2480.00"),
                           low=Decimal("2410.00"), timestamp=102.0)
    assert fills == []
    assert stop.order_id in broker.pending_orders

    # Bar low 2390: stop triggered, fills at market with slippage (below 2400).
    fills = broker.on_tick(price=Decimal("2395.00"), high=Decimal("2405.00"),
                           low=Decimal("2390.00"), timestamp=103.0)
    assert len(fills) == 1
    assert fills[0].side == OrderSide.SELL
    assert fills[0].price < Decimal("2400.00")
    assert fills[0].price > Decimal("2390.00")
    assert p.position_qty == Decimal("0.0000")


def test_take_profit_fill_pays_slippage():
    """Item 5: TP fills pay the same slippage as SL fills (symmetric exits)."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    ticket = OrderTicket(
        portfolio_id="p1", symbol="ETH/USD", side=OrderSide.BUY,
        order_type=OrderType.MARKET, qty=Decimal("0.4"),
        stop_loss=Decimal("2450.00"), take_profit=Decimal("2600.00"), timestamp=100.0,
    )
    assert broker.submit_order(ticket) is not None
    fills = broker.on_tick(price=Decimal("2510.00"), high=Decimal("2620.00"),
                           low=Decimal("2495.00"), timestamp=101.0,
                           open_price=Decimal("2505.00"))
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.TAKE_PROFIT
    assert fills[0].price < Decimal("2600.00")
    assert fills[0].price > Decimal("2599.00")
    assert p.position_qty == Decimal("0.0000")
'''

app("tests/test_broker_sim.py", "def test_limit_buy_waits_until_price_reaches_limit", NEW_TESTS)



# ---------------------------------------------------------------- verify + apply
def main():
    files = {}
    for rel, _old, _new in REPLACEMENTS:
        files.setdefault(rel, _read(ROOT / rel))
    for rel, _marker, _text in APPENDS:
        files.setdefault(rel, _read(ROOT / rel))

    for rel, old, _new in REPLACEMENTS:
        text, _crlf = files[rel]
        n = text.count(old)
        assert n == 1, f"{rel}: expected exactly 1 occurrence, found {n}: {old[:100]!r}"
    for rel, marker, _text in APPENDS:
        text, _crlf = files[rel]
        assert marker not in text, f"{rel}: marker already present: {marker!r}"
    print(f"All {len(REPLACEMENTS)} anchors verified, {len(APPENDS)} append markers clear.")

    new_texts = {rel: text for rel, (text, _c) in files.items()}
    for rel, old, new in REPLACEMENTS:
        new_texts[rel] = new_texts[rel].replace(old, new, 1)
    for rel, _marker, text in APPENDS:
        cur = new_texts[rel]
        if not cur.endswith("\n"):
            cur += "\n"
        new_texts[rel] = cur + text
    for rel, text in new_texts.items():
        _write(ROOT / rel, text, files[rel][1])
        print(f"patched {rel}")
    print("ITEM5 PATCH OK")


if __name__ == "__main__":
    main()
