import asyncio
import re
import threading
from typing import Optional

from pynput import keyboard

from trading_app.bus import CommandEvent, CommandType
from trading_app.trading_config import TradingConfig
from trading_app.services.trade_instruction_factory import TradeInstructionFactory


class HotkeyManager:
    """YAML-driven hotkey manager for the local trading app."""

    def __init__(
        self,
        *,
        trading_config: Optional[TradingConfig] = None,
        runtime=None,
        trade_instruction_factory=None,
    ):
        self.trading_config = trading_config
        self.runtime = runtime
        self.trade_instruction_factory = trade_instruction_factory
        self.loop = None
        self.queue = asyncio.Queue()
        self._bindings = {}

        if self.trading_config is None:
            from trading_app.config import AppConfig
            from trading_app.trading_config import TradingConfig

            self.trading_config = TradingConfig.load(
                AppConfig.load().get_trading_config_path()
            )

        if self.trade_instruction_factory is None:
            self.trade_instruction_factory = TradeInstructionFactory(
                config=self.trading_config,
            )

        self._bindings = {}
        for combo, target in self.trading_config.hotkeys.items():
            normalized = self._normalize_combo(combo)
            if normalized:
                self._bindings[normalized] = self.make_handler(target)

    @staticmethod
    def _normalize_combo(combo: str) -> str:
        combo = combo.strip().lower()
        if not combo:
            return ""

        tokens = [token.strip() for token in re.split(r"\s*\+\s*", combo) if token.strip()]
        if not tokens:
            return ""

        normalized = []
        for token in tokens:
            if token in {"ctrl", "control"}:
                normalized.append("<ctrl>")
            elif token == "shift":
                normalized.append("<shift>")
            elif token == "alt":
                normalized.append("<alt>")
            elif token in {"esc", "escape"}:
                normalized.append("<esc>")
            elif token in {"enter", "return"}:
                normalized.append("<enter>")
            elif token in {"tab"}:
                normalized.append("<tab>")
            else:
                normalized.append(token)

        return "+".join(normalized)

    def make_handler(self, template_name: str):
        def handler():
            self.enqueue_action(template_name)
        return handler

    def resolve_hotkey_target(self, combo: str) -> Optional[str]:
        return self.trading_config.hotkeys.get(combo)

    def start(self):
        threading.Thread(target=self.start_async_loop, daemon=True).start()
        threading.Thread(target=self.start_hotkeys, daemon=True).start()
        print("Hotkeys running...")

    def start_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.worker())
        self.loop.run_forever()

    def start_hotkeys(self):
        with keyboard.GlobalHotKeys(self._bindings) as listener:
            listener.join()

    def enqueue_action(self, template_name: str):
        if self.loop is None:
            return

        asyncio.run_coroutine_threadsafe(
            self.queue.put(template_name),
            self.loop,
        )

    async def worker(self):
        while True:
            template_name = await self.queue.get()
            try:
                await self.handle_template(template_name)
            except Exception as exc:
                print("Hotkey error:", exc)
            finally:
                self.queue.task_done()

    async def handle_template(self, template_name: str):
        if self.runtime is None:
            print(f"Hotkey target {template_name} ignored: runtime not attached")
            return

        if self.runtime.running is False:
            print(f"Hotkey target {template_name} ignored: runtime not running")
            return

        symbol = None
        if hasattr(self.runtime, "gui") and self.runtime.gui is not None:
            symbol = self.runtime.gui.get_selected_symbol()

        if not symbol:
            print(f"Hotkey target {template_name} ignored: no symbol selected")
            return

        template = self.trading_config.templates.get(template_name)
        if template is None:
            print(f"Hotkey target {template_name} ignored: template not configured")
            return

        if template.action is not None:
            self._handle_action(template.action)
            return

        if self.runtime.gui is not None and hasattr(self.runtime.gui, "trade_instruction_panel"):
            panel = self.runtime.gui.trade_instruction_panel
            instruction = panel.apply_template_to_panel(
                template_name,
                quote=self.runtime.state_engine.get_quote(symbol),
            )
            panel._submit(instruction.side)
            return

        instruction = self.trade_instruction_factory.create(
            template_name=template_name,
            symbol=symbol,
            quote=self.runtime.state_engine.get_quote(symbol),
        )

        self.runtime.submit_instruction(instruction)

    def _handle_action(self, action: str):
        if self.runtime is None:
            return

        command = None
        if action == "FLATTEN":
            command = CommandType.FLATTEN
        elif action == "CANCEL_ALL":
            command = CommandType.CANCEL
        elif action == "PANIC_EXIT":
            command = CommandType.PANIC
        elif action == "REFRESH_QUOTES":
            self.runtime.refresh_positions()
            return

        if command is not None and self.runtime.loop is not None:
            event = CommandEvent(command=command, payload=None)
            asyncio.run_coroutine_threadsafe(
                self.runtime.bus.publish_command(event),
                self.runtime.loop,
            )


if __name__ == "__main__":
    HotkeyManager().start()
