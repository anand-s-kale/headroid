# headroid (Python host)

Host-side SDK and CLI for the headroid device server. No runtime dependencies; needs `adb` on PATH.

```python
from headroid import Device

dev = Device.connect(serial="R58M...", jar="headroid-server.jar")  # pushes and starts the server
print(dev.info())

display = dev.create_display(720, 1600, 320)   # hidden virtual display
display.launch("dev.headroid.sample")
btn = display.find(rid="login_button")         # or text=..., desc=...
l, t, r, b = btn["bounds"]
display.tap((l + r) // 2, (t + b) // 2)
display.screenshot("shot.png")
print(display.tree())

dev.close()
```

CLI smoke tests (`--serial` is required when more than one device is attached):

```
headroid info --serial R58M... --jar headroid-server.jar
headroid screenshot --serial R58M... --jar headroid-server.jar -o shot.png
headroid tree --serial R58M... --jar headroid-server.jar
```

Tests: `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]" && python -m pytest -q`
(they use a fake JSON-RPC server and a fake adb; no phone needed).
