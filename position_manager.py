"""
Position Manager - Mengelola posisi aktif dan history sinyal.
"""
import json
import logging
import os
import time

from config import CL_PERCENT, TP_PERCENT

logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "positions.json")


class Position:
    """Representasi satu posisi trading."""

    def __init__(
        self,
        pair: str,
        entry_price: float,
        signal_time: float,
        tp_percent: float = TP_PERCENT,
        cl_percent: float = CL_PERCENT,
    ):
        self.pair = pair
        self.entry_price = entry_price
        self.signal_time = signal_time
        self.tp_price = entry_price * (1 + tp_percent / 100)
        self.cl_price = entry_price * (1 - cl_percent / 100)
        self.tp_percent = tp_percent
        self.cl_percent = cl_percent

    def check_tp(self, current_price: float) -> bool:
        """Cek apakah harga sudah mencapai Take Profit."""
        return current_price >= self.tp_price

    def check_cl(self, current_price: float) -> bool:
        """Cek apakah harga sudah mencapai Cut Loss."""
        return current_price <= self.cl_price

    def profit_percent(self, current_price: float) -> float:
        """Hitung persentase profit/loss saat ini."""
        return ((current_price - self.entry_price) / self.entry_price) * 100

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "entry_price": self.entry_price,
            "signal_time": self.signal_time,
            "tp_price": self.tp_price,
            "cl_price": self.cl_price,
            "tp_percent": self.tp_percent,
            "cl_percent": self.cl_percent,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        pos = cls(
            pair=data["pair"],
            entry_price=data["entry_price"],
            signal_time=data["signal_time"],
            tp_percent=data.get("tp_percent", TP_PERCENT),
            cl_percent=data.get("cl_percent", CL_PERCENT),
        )
        pos.tp_price = data["tp_price"]
        pos.cl_price = data["cl_price"]
        return pos


class PositionManager:
    """Mengelola semua posisi aktif."""

    def __init__(self):
        self.positions: dict[str, Position] = {}
        self.history: list[dict] = []
        self._load()

    def _load(self) -> None:
        """Load posisi dari file."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE) as f:
                    data = json.load(f)
                for pair, pos_data in data.get("positions", {}).items():
                    self.positions[pair] = Position.from_dict(pos_data)
                self.history = data.get("history", [])
                logger.info("Loaded %d posisi aktif", len(self.positions))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Gagal load positions.json: %s", e)

    def _save(self) -> None:
        """Simpan posisi ke file."""
        data = {
            "positions": {
                pair: pos.to_dict() for pair, pos in self.positions.items()
            },
            "history": self.history[-100:],  # Simpan 100 history terakhir
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def has_position(self, pair: str) -> bool:
        return pair.upper() in self.positions

    def open_position(
        self,
        pair: str,
        entry_price: float,
        tp_percent: float = TP_PERCENT,
        cl_percent: float = CL_PERCENT,
    ) -> Position:
        """Buka posisi baru dengan TP/CL yang bisa di-override (ATR-based)."""
        pair = pair.upper()
        pos = Position(
            pair=pair,
            entry_price=entry_price,
            signal_time=time.time(),
            tp_percent=tp_percent,
            cl_percent=cl_percent,
        )
        self.positions[pair] = pos
        self._save()
        logger.info("Opened position %s @ %.8f", pair, entry_price)
        return pos

    def close_position(self, pair: str, close_price: float, reason: str) -> dict:
        """Tutup posisi dan simpan ke history."""
        pair = pair.upper()
        pos = self.positions.pop(pair, None)
        if pos is None:
            return {}

        pnl = pos.profit_percent(close_price)
        record = {
            "pair": pair,
            "entry_price": pos.entry_price,
            "close_price": close_price,
            "pnl_percent": round(pnl, 2),
            "reason": reason,
            "entry_time": pos.signal_time,
            "close_time": time.time(),
        }
        self.history.append(record)
        self._save()
        logger.info("Closed position %s @ %.8f (%s, PnL: %.2f%%)",
                     pair, close_price, reason, pnl)
        return record

    def check_positions(self, pair: str, current_price: float) -> dict | None:
        """
        Cek apakah posisi pair tertentu sudah mencapai TP atau CL.

        Returns:
            dict dengan info close atau None.
        """
        pair = pair.upper()
        pos = self.positions.get(pair)
        if pos is None:
            return None

        if pos.check_tp(current_price):
            return self.close_position(pair, current_price, "TAKE_PROFIT")

        if pos.check_cl(current_price):
            return self.close_position(pair, current_price, "CUT_LOSS")

        return None

    def get_status(self) -> list[dict]:
        """Get status semua posisi aktif."""
        result = []
        for pair, pos in self.positions.items():
            result.append({
                "pair": pair,
                "entry_price": pos.entry_price,
                "tp_price": pos.tp_price,
                "cl_price": pos.cl_price,
            })
        return result
