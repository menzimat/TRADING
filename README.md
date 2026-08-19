source ~/p39env/bin/activate
cd ~/Projects/python/SINGLE_TRADING_APP
cd ~/Projects/python/TRADING_SCANNER/TRADING
python -m compileall src/trading_app
pip install -e .

PYNPUT_BACKEND=dummy PYTHONPATH=src python -m unittest -q \
  tests.test_hotkeys \
  tests.test_command_processor \
  tests.test_runtime_gui_events \
  tests.test_manual_price_override \
  tests.test_runtime_symbol_subscription

OR

PYTHONPATH=src python -m unittest -q   tests.test_hotkeys   tests.test_command_processor   tests.test_runtime_gui_events   tests.test_manual_price_override   tests.test_runtime_symbol_subscription tests.test_percent_position_sizing

python -m trading_app.schwab_streamer

#
#
#
python3 - <<'PY'
import numpy as np
import sounddevice as sd
import time

rate = 48000
duration = 0.5
frequency = 880

t = np.arange(int(rate * duration)) / rate
x = 0.25 * np.sin(2 * np.pi * frequency * t)

print("Playing 880 Hz tone on device 25 (pipewire)...")
sd.play(x.astype(np.float32), rate, device=25)
sd.wait()
print("Done")
PY

#
#
#
python3 - <<'PY'
import numpy as np
import sounddevice as sd

rate = 48000
duration = 0.5
frequency = 880

t = np.arange(int(rate * duration)) / rate
x = 0.25 * np.sin(2 * np.pi * frequency * t)

print("Playing 880 Hz tone on Jabra device 11...")
sd.play(x.astype(np.float32), rate, device=11)
sd.wait()
print("Done")
PY

#
#
#

python3 - <<'PY'
import numpy as np
import sounddevice as sd

rate = 48000
duration = 0.5
frequency = 880

t = np.arange(int(rate * duration)) / rate
x = 0.25 * np.sin(2 * np.pi * frequency * t)

print("Playing 880 Hz tone on default device...")
sd.play(x.astype(np.float32), rate)
sd.wait()
print("Done")
PY

