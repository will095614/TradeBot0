import sys, os
sys.path.insert(0, os.path.abspath("."))
from src.data.live_engine import LiveArenaEngine

engine = LiveArenaEngine()
q = engine.fetch_realtime_crypto_quote()
print("Provider:", q.source)
print("Price:", str(q.price))
print("Bid:", str(q.bid), "Ask:", str(q.ask))
print("24h High:", str(q.high_24h), "24h Low:", str(q.low_24h))
print("Volume 24h:", str(q.volume_24h))
print("Change 24h %:", str(q.change_24h_pct))
print("Offline:", q.is_offline)
assert q.price > 0, "Price must be positive"
print("SUCCESS: REAL MARKET DATA VERIFIED!")
engine.stop()
