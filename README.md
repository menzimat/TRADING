source ~/p39env/bin/activate
cd ~/Projects/python/SINGLE_TRADING_APP
python -m compileall src/trading_app
pip install -e .

PYNPUT_BACKEND=dummy PYTHONPATH=src python -m unittest -q \
  tests.test_hotkeys \
  tests.test_command_processor \
  tests.test_runtime_gui_events \
  tests.test_manual_price_override \
  tests.test_runtime_symbol_subscription

OR

PYTHONPATH=src python -m unittest -q \
  tests.test_hotkeys \
  tests.test_command_processor \
  tests.test_runtime_gui_events \
  tests.test_manual_price_override \
  tests.test_runtime_symbol_subscription

python -m trading_app.schwab_streamer
