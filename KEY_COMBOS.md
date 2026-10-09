# CIDOO ABM066 — On-Keyboard Cheatsheet

Everything the keyboard does **by itself**, without VIA or any host software.
Compiled from the official CIDOO ABM066 manual (1-page PDF), the
`CIDOO ABM066-USB.JSON` VIA definition, and a hardware test pass.

---

## 1. Mode switch (top-left, 3 positions)

Left to right: **BT → Wired → 2.4G**

| Position | Mode | How to connect |
|---|---|---|
| Left | Bluetooth 5.0 (3 devices) | Hold `FN+Q` / `FN+W` / `FN+E` for **3–5 s** to pair. Screen `BT1/2/3` icon flashes fast, then goes solid. |
| Middle | Wired USB | Plug the USB cable in. Screen lights up = connected. |
| Right | 2.4 GHz | Plug the receiver in. Already paired from the factory. |

Device names for pairing: `CIDOO ABM066-1` (`FN+Q`), `CIDOO ABM066-2` (`FN+W`),
`CIDOO ABM066-3` (`FN+E`).

To **switch between already-paired** Bluetooth devices: short press `FN+Q`,
`FN+W` or `FN+E` (no hold).

To **re-pair the 2.4 GHz receiver**: hold `FN+R` for **3–5 s** until the 2.4G
icon flashes fast, then plug the receiver into USB.

> The keyboard remembers the last Bluetooth device and reconnects to it when
> powered on.

---

## 2. Default hotkeys — hold `FN` + key

### System mode

| Keys | Action |
|---|---|
| `FN+A` | Windows mode |
| `FN+S` | Mac mode |

In Mac mode: `Left Alt` = Left Option, `Left Win` = Left Command,
`Right Alt` = Right Option.

### F-row (the number row doubles as F1–F12)

| Keys | Action | Keys | Action |
|---|---|---|---|
| `FN+1!` | F1 | `FN+7&` | F7 |
| `FN+2@` | F2 | `FN+8*` | F8 |
| `FN+3#` | F3 | `FN+9(` | F9 |
| `FN+4$` | F4 | `FN+0)` | F10 |
| `FN+5%` | F5 | `FN+-_` | F11 |
| `FN+6^` | F6 | `FN+=+` | F12 |

### Navigation

| Keys | Action |
|---|---|
| `FN+PG UP` | Insert |
| `FN+PG DN` | Delete |

### Screen (LCD)

| Keys | Action |
|---|---|
| `FN+ENTER` | Toggle LCD profile — this is how you cycle back to the clock view after a custom animation |
| `FN+X` | LCD on / off |
| `FN+ESC` | **Hold 3 s** = factory reset the keyboard |

---

## 3. Layers

Four layers, 0–3. Layer 0 is selected automatically by OS mode; the others are
momentary and activated by holding a remapped key.

| Layer | Activated by | Notes |
|---|---|---|
| 0 | Automatic | Win mode or Mac mode, chosen by `FN+A` / `FN+S` |
| 1 | Hold the key remapped to `Fn1(3)` | Ships on the base layer |
| 2 | Hold the key remapped to `MO(2)` | Must be set in VIA |
| 3 | Hold the key remapped to `MO(3)` | Must be set in VIA |

Any single key can carry a different function per layer.

---

## 4. Keycap legends / VIA special keys

These are the factory remappable special keys. Names are as they appear in VIA.

| Legend | Meaning | Legend | Meaning |
|---|---|---|---|
| `Hue+` | Hue increase | `Lock Win` | Lock the Windows key |
| `Hue-` | Hue decrease | `USB Mode` | Switch to USB (wired) mode |
| `Sat+` | Light saturation + | `Win...` | Windows mode |
| `Sat-` | Light saturation − | `Mac...` | Mac mode |
| `RGB Md+` | Next RGB effect | `Fn1(3)` | Layer 1 while held |
| `RGB Tog...` | RGB on / off | `MO(2)` | Layer 2 while held |
| `RGB SPD` | RGB speed − | `MO(3)` | Layer 3 while held |
| `RGB SPI` | RGB speed + | `BT 1` / `BT 2` / `BT 3` | Bluetooth device 1 / 2 / 3 |
| `Brght+` | Backlight + | | |
| `Brght-` | Backlight − | | |

VIA also adds these custom keycodes (`CIDOO ABM066-USB.JSON`):

`2.4G MODE`, `Bluetooth 1/2/3`, `WIN MODE`, `MAC MODE`,
`DESKTOP LIGHT LOW`, `DESKTOP LIGHT HIGH`, `OLED SET`,
`LED LOGO MODE`, `LED LOGO COLOUR`, `OLED POWER`

---

## 5. Screen (TFT-LCD)

- **Two** user-customisable slots — one animation/image each — plus the
  built-in views (clock among them).
- `FN+ENTER` cycles the display profile; `FN+X` turns the LCD off/on.
- Custom slots are written with the Windows **Image Custom Tool**
  (`Import animation` / `Import image` → `Upload all frames`), or from Linux
  with a reimplementation. Uploading *replaces* that slot — this is how a
  custom animation can end up where the clock used to be.

---

## 6. Power, sleep and charging

| Condition | Behaviour |
|---|---|
| BT / 2.4G, idle **3 min** | Backlight and LCD turn off. Any key wakes. |
| BT, idle **30 min** | Deep sleep, Bluetooth disconnects. Any key wakes, LCD lights, reconnects. |
| Battery low | Screen shows a low-battery warning and the battery icon turns red. The manual quotes `<3.3 V` (Chinese) and `<3.5 V` (English) — treat it as roughly 3.3–3.5 V. |
| Charging | Charging icon shown top-right of the screen. |

Wired mode never sleeps.

---

## 7. Notes / gotchas

- The **mode switch position beats the cable**: with the switch on BT or 2.4G,
  plugging in USB only charges — the keyboard does not enumerate as a USB
  device. Vendor HID features (screen upload, clock) need the **middle
  (wired)** position.
- The manual's key-description table has two transcription slips: the
  `Hue-` row is labelled "Light Saturation−" and the `Sat-` row likewise.
  Treat `Hue±` as hue and `Sat±` as saturation.
- `FN+R` (2.4G pairing) is only documented in the English column of the
  manual, not in the Chinese one.
