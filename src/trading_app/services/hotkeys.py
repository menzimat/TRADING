import asyncio
import re
from typing import Optional

from trading_app.bus import CommandEvent, CommandType
from trading_app.trading_config import TradingConfig
from trading_app.services.trade_instruction_factory import TradeInstructionFactory

class HotkeyManager:
    """YAML-driven hotkey manager for the local trading app."""

    _SHIFT_MAP = {
        "!": "1",
        "@": "2",
        "#": "3",
        "$": "4",
        "%": "5",
        "^": "6",
        "&": "7",
        "*": "8",
        "(": "9",
        ")": "0",
    }

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


    def resolve_hotkey_target(self, combo: str):

        target = self.trading_config.hotkeys.get(combo)

        if target is None:
            return None

        #
        # OLD STYLE
        #
        # ctrl+b: buy_limit
        #
        if isinstance(target, str):

            template = self.trading_config.templates.get(target)

            if template is None:
                return None

            return {
                "template_name": target,
                "overrides": None,
            }
        elif "action" in target:
            return {
                "action": target["action"]
            }
        #
        # NEW STYLE
        #
        # shift+2:
        #   template: buy_limit
        #   overrides: ...
        #
        elif isinstance(target, dict):

            template_name = target["template"]

            template = self.trading_config.templates.get(template_name)

            if template is None:
                return None

            return {
                "template_name": template_name,
                "overrides": target.get("overrides"),
            }

        return None



    async def execute_hotkey(self, resolved):

        try:
            print("HOTKEY:", resolved)

            if (
                self.runtime is None
                or not self.runtime.running
                or self.runtime.loop is None
                or not self.runtime.hotkeys_enabled
            ):
                print("HOTKEY: runtime not ready")
                return

            action = resolved.get("action")

            if action:
                print("ACTION:", action)
                self._handle_action(action)
                return


            template_name = resolved.get("template_name")

            if not template_name:
                print("HOTKEY ERROR: no action or template")
                return


            symbol = self.runtime.gui.get_selected_symbol()

            if not symbol:
                print("No SYMBOL: Exiting")
                return


            panel = self.runtime.gui.trade_instruction_panel

            instruction = panel.apply_template_to_panel(
                template_name,
                quote=self.runtime.state_engine.get_quote(symbol),
                review_before_send=self.runtime.gui.trade_instruction_panel.get_review_setting() ,
                template_override=resolved.get("overrides"),
            )

            if instruction is None:
                print("HOTKEY: no instruction created")
                return
            
            print("Submitting Instruction:", instruction)
            panel._submit(instruction.side)

        except Exception:
            import traceback
            traceback.print_exc()

    def _handle_action(self, action: str):
        if self.runtime is None:
            return

        command = None
        request = None
        if action == "FLATTEN":
            command = CommandType.FLATTEN
            symbol = self.runtime.gui.get_selected_symbol()

            if not symbol:
                print("FLATTEN: no symbol selected")
                return

            print("FLATTEN SYMBOL:", symbol)

            self.runtime.flatten_position(symbol)
            return
        elif action == "CANCEL_ALL":
            command = CommandType.CANCEL_ALL
            self.runtime.cancel_all_orders()
            return
        elif action == "PANIC_EXIT":
            command = CommandType.PANIC
        elif action == "REFRESH_QUOTES":
            self.runtime.refresh_positions()
            return

        if command is not None and self.runtime.loop is not None:
            event = CommandEvent(command=command, payload=request)
            asyncio.run_coroutine_threadsafe(
                self.runtime.bus.publish_command(event),
                self.runtime.loop,
            )



    def event_to_combo(self, event):

        modifiers = []

        #
        # Modifiers
        #

        if event.state & 0x0004:
            modifiers.append("ctrl")

        if event.state & 0x0001:
            modifiers.append("shift")

        if event.state & 0x0008:
            modifiers.append("alt")


        #
        # Key normalization
        #

        keysym = event.keysym.lower()

        if keysym == "escape":
            key = "esc"

        elif event.state & 0x0004:
            # Ctrl keys: ignore event.char control codes
            key = keysym

        elif event.char:
            key = event.char.lower()
            key = self._SHIFT_MAP.get(key, key)

        else:
            key = keysym


        modifiers.append(key)

        return "+".join(modifiers)
    
    def _hotkey_done(self, future):

        try:
            future.result()

        except Exception:
            import traceback
            traceback.print_exc()

    def handle_key_event(self, event):

        combo = self.event_to_combo(event)
        widget = event.widget

        if widget.winfo_class() in ("Entry", "TEntry", "Text"):

            # Ignore printable characters typed into text fields.
            # Still allow Esc, Ctrl+*, F-keys, etc.
            if event.char and event.char.isprintable():
                return
            
        print("HOTKEY COMBO:", repr(combo))

        resolved = self.resolve_hotkey_target(combo)

        if not resolved:
            print("handle_key_event: UNRESOLVED HOTKEY")
            return


        #
        # Runtime readiness check
        #
        if self.runtime is None:
            print("HOTKEY IGNORED: runtime unavailable")
            return

        if not self.runtime.running:
            print("HOTKEY IGNORED: runtime not running")
            return

        if self.runtime.loop is None:
            print("HOTKEY IGNORED: asyncio loop not ready")
            return


        future = asyncio.run_coroutine_threadsafe(
            self.execute_hotkey(resolved),
            self.runtime.loop,
        )

        future.add_done_callback(self._hotkey_done)


#if __name__ == "__main__":
#    exit