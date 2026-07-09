import asyncio
import threading
import httpx
from enum import Enum, auto
from pynput import keyboard

#from trading_app.HK_gui import run
from trading_app.shared_state import state
from trading_app.config import AppConfig

cfg = AppConfig()

# BASE_URL = f"http://{cfg.app_ip}:{cfg.app_port}"
BASE_URL = "http://localhost"

queue = asyncio.Queue()
loop = None


class TradeAction(Enum):
    BUY = auto()
    SELL = auto()
    FLATTEN = auto()
    CANCEL = auto()
    PANIC = auto()
    QUOTES = auto()

class HotkeyManager:
    HOTKEYS = {
        "<ctrl>+b": TradeAction.BUY,
        "<ctrl>+s": TradeAction.SELL,
        "<shift>+f": TradeAction.FLATTEN,
        "<esc>": TradeAction.CANCEL,
        "<ctrl>+<shift>+q": TradeAction.PANIC,
        "<ctrl>+<shift>+u": TradeAction.QUOTES,
    }

    def __init__(self):
        self.bindings = {
            combo: self.make_handler(action)
            for combo, action in self.HOTKEYS.items()
        }

    def make_handler(self, action):
        def handler():
            self.enqueue_action(action)
        return handler

    def start(self):
        threading.Thread(target=self.start_async_loop, daemon=True).start()
        threading.Thread(target=self.start_hotkeys, daemon=True).start()

        print("Hotkeys running...")
#       run()

    def start_async_loop(self):
        global loop

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.create_task(self.worker())
        loop.run_forever()

    def start_hotkeys(self):
        with keyboard.GlobalHotKeys(self.bindings) as listener:
            listener.join()

    def build_payload(self, action):
        if action == TradeAction.QUOTES:
            return state.tickers

        return {
            "symbol": state.symbol,
            "qty": state.qty,
        }

    async def call_api(self, action, payload):
        transport = httpx.AsyncHTTPTransport(uds=cfg.socket_path)

        async with httpx.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            if action == TradeAction.QUOTES:
                params = [("symbols", s) for s in payload]
                r = await client.get("/quotes", params=params)
            else:
                endpoint_map = {
                    TradeAction.BUY: "/buy_market",
                    TradeAction.SELL: "/sell_market",
                    TradeAction.FLATTEN: "/flatten",
                    TradeAction.CANCEL: "/cancel_all",
                    TradeAction.PANIC: "/panic_exit",
                }
                r = await client.post(
                    endpoint_map[action],
                    json=payload,
                )

            r.raise_for_status()
            return r.json()

    async def worker(self):
        while True:
            action, payload = await queue.get()

            try:
                await self.call_api(action, payload)
            except Exception as e:
                print("Worker error:", e)
            finally:
                queue.task_done()

    def enqueue_action(self, action):
        payload = self.build_payload(action)
        asyncio.run_coroutine_threadsafe(
            queue.put((action, payload)),
            loop,
        )


if __name__ == "__main__":
    HotkeyManager().start()
