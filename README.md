# abm066-lcd-clock

Set the clock on a **CIDOO ABM066** mechanical keyboard's TFT-LCD from Linux —
no Windows, no Wine, no vendor software.

The ABM066's clock is only settable with the Windows-only *Image Custom Tool*,
so on Linux it drifts indefinitely. This is a small Python script that speaks
the keyboard's HID protocol directly, plus a systemd timer and a Home Manager
module to keep it honest.

```
$ ./abm066_clock.py read
Device      : /dev/hidraw10
Host time   : 2026-10-09 21:14:23
LCD clock now: 2026-05-16 10:56:56 (Sat)     <- stuck since May

$ ./abm066_clock.py set
LCD clock now: 2026-10-09 21:16:35 (Fri)     <- fixed
```

## Requirements

- Linux with the keyboard plugged in over **USB**
- Python 3 (no third-party modules needed for the protocol)

`python-hidapi` is optional and only used by the `list` subcommand.

## ⚠️ It only works over USB

The keyboard's vendor screen interface exists **only in wired mode**. Put the
mode switch (top-left) in the middle position and use a data cable:

```
[ BT ] [ WIRED ] [ 2.4G ]
```

Over Bluetooth the `0xFF1C:0x92` HID collection does not exist at all — in the
Bluetooth report descriptor, report ID 4 is the *mouse*. Over 2.4 GHz the
vendor interface is behind the dongle. There is no Bluetooth path to the clock.

The clock is stored in the keyboard, so syncing once over USB is enough — you
can go back to Bluetooth afterwards.

## Usage

```sh
./abm066_clock.py list          # show HID interfaces and find the screen one
./abm066_clock.py read          # read the current record (non-mutating query)
./abm066_clock.py dry-run       # show the exact before/after bytes, write nothing
./abm066_clock.py set           # write the host clock to the keyboard
```

| Option | Meaning |
| --- | --- |
| `--slot N` | Config slot to use; default `0` |
| `--at 'YYYY-MM-DDTHH:MM:SS'` | Use a fixed time instead of the host clock |
| `--save-template PATH` | Save the record read from the device as a backup |
| `--device /dev/hidrawN` | Skip auto-detection |
| `--quiet` | Exit `0` silently when the keyboard isn't on USB (for timers) |
| `--debug` | Dump every HID packet |

`read` and `set` are safe to run repeatedly, but each `set` rewrites flash — see
[Safety](#safety).

## Automatic re-sync

The record does not tick (see [Findings](#findings)), so the internal RTC is
free-running from whatever was last written and will drift again. Two options:

### systemd (user units)

```sh
./install.sh          # installs to ~/.local/bin + ~/.config/systemd/user
systemctl --user enable --now abm066-clock.timer
```

Fires 1 minute after login, then every 6 hours. When the keyboard isn't in
wired mode the service finds nothing, exits `0`, and stays quiet.

### NixOS / Home Manager

`nix/abm066-clock.nix` is the same setup as a Home Manager module:

```nix
imports = [ ./hardware/abm066-clock.nix ];
```

The module also documents the equivalent `services.udev.extraRules` for
granting hidraw access, and a variant that syncs on plug-in instead of on a
timer.

## How it works

The clock lives in a **48-byte config record** in the keyboard's flash. Bytes
35..41 are the date and time in packed BCD (`bcd(n) = ((n / 10) << 4) | (n % 10)`):

| Offset | Field |
| ---: | --- |
| 35 | seconds |
| 36 | minutes |
| 37 | hours (24 h, local) |
| 38 | weekday — Sunday `0` … Saturday `6` |
| 39 | day of month |
| 40 | month |
| 41 | two-digit year |

Every packet is 64 bytes:

```
byte 0      report id 0x04
byte 1..2   checksum = sum(packet[3..63]) & 0xffff, little-endian
byte 3      command
byte 4..    command payload
```

Setting the clock is a **read-modify-write**:

| Step | Command | Purpose |
| --- | --- | --- |
| 1 | `0x05` × 12 | Read the existing 48-byte record in 4-byte chunks at offset `slot * 0x31` |
| 2 | `0x01` | Begin session |
| 3 | `0x06` | Write the patched 48-byte record |
| 4 | `0x02` | Commit (the Windows tool sleeps ~10 ms before this) |

## Safety

- **Always read-modify-write.** The script reads the current record and patches
  only bytes 35..41, preserving layer, animation, brightness and frame-count
  settings. A hardcoded template would clobber them.
- It refuses an all-zero record (wrong collection / failed read), refuses a
  response that is merely an echo of the request, and asserts internally that
  no non-time byte would change.
- **`set` writes flash.** Don't loop it on a short interval. The bundled timer
  is 6-hourly on purpose.
- Back up before the first write:

  ```sh
  ./abm066_clock.py read --save-template cidoo-record.bin
  ```

  Note this backs up the 48-byte config record only, not the custom image store.
- The device node is usually `root:users 0660`, so a user in `users` needs no
  root and no extra udev rule.

## Findings

Things established by testing against real hardware while building this:

- **The record is a set-point, not a live readout.** Read it twice 20 seconds
  apart and bytes 35..41 are byte-identical. The RTC that drives the display is
  internal and free-running from that value. A one-shot sync therefore holds,
  and re-syncing is insurance rather than a necessity.
- **Config offset 33 is the active LCD profile selector**, and the keyboard
  rewrites it itself when you press `FN+ENTER`. It flipped `0x02 → 0x00` on its
  own during testing. This is the strongest argument for read-modify-write: a
  hardcoded template silently breaks the active screen view.
- **An echo is not acceptance.** The keyboard echoes output reports back on the
  input endpoint at the transport layer. Every earlier attempt that treated this
  echo as success was chasing a HID acknowledgement, not firmware acceptance.

## Key combos

[`KEY_COMBOS.md`](KEY_COMBOS.md) is a complete cheatsheet of what the keyboard
does by itself: mode switch behaviour, every `FN` hotkey, the four layers and
which key activates each, every keycap legend (`Hue±`, `RGB Md+`, `MO(2)`…),
and the sleep/charging rules.

## Credits

The HID protocol was **not** discovered here. It comes from
**[ricardobeat/cidoo-abm066-tool](https://github.com/ricardobeat/cidoo-abm066-tool)**,
which reverse-engineered the Windows *Image Custom Tool* (the record writer is
function `0x49f5c0`) and documented it in
[CIDOO_ABM066_SCREEN_PROTOCOL.md](https://github.com/ricardobeat/cidoo-abm066-tool/blob/main/CIDOO_ABM066_SCREEN_PROTOCOL.md).
Their work saved an enormous amount of time, and their notes on packet framing,
the checksum, the config record and the begin/commit sequence are the basis for
this implementation. That project also targets macOS and image upload; this one
is the Linux clock-only counterpart.

Thanks also to the earlier community notes on the ABM066 screen resolution and
GIF handling that informed the protocol document.

What this repo adds on top: a dependency-light Linux implementation, strict
read-modify-write safety checks, the empirical findings above, an on-keyboard
cheatsheet, and systemd / Home Manager integration.

## License

MIT — see [LICENSE](LICENSE).

The `Image Custom Tool` and the ABM066 manual are property of their respective
owners and are deliberately not redistributed here.
