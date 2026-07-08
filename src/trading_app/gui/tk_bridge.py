# tk_bridge.py
import asyncio

class TkBridge:
    def __init__(self, root, bus, ui_callback):
        self.root = root
        self.bus = bus
        self.ui_callback = ui_callback
        self.running = True

    def start(self):
        self.root.after(0, self._pump)

    def stop(self):
        self.running = False

    def _pump(self):
        if not self.running:
            return

        try:
            # drain all pending events (non-blocking)
            while not self.bus.queue.empty():
                event = self.bus.queue.get_nowait()
                self.ui_callback(event)

        except Exception as e:
            print("Bridge error:", e)

        self.root.after(16, self._pump)  # ~60fps UI tick
