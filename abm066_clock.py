#!/usr/bin/env python3
"""CIDOO ABM066 LCD clock sync for Linux (USB, wired mode).

Protocol source: ricardobeat/cidoo-abm066-tool, CIDOO_ABM066_SCREEN_PROTOCOL.md
Static analysis of the Windows "Image Custom Tool" (function 0x49f5c0).

The keyboard keeps a 48-byte "screen/clock config record" in flash. The
displayed time is decoded from packed-BCD bytes 35..41 of that record:

    35  seconds   BCD 00..59
    36  minutes   BCD 00..59
    37  hours     BCD 00..23   (24h local time)
    38  weekday   0=Sunday .. 6=Saturday
    39  day       BCD 01..31
    40  month     BCD 01..12
    41  year      BCD 00..99   (two digit)

Writing the clock is a read-modify-write, never a from-scratch packet:

    1. read the current 48-byte record   (cmd 0x05, 4-byte chunks)
    2. patch ONLY bytes 35..41 from the host clock
    3. begin session                     (cmd 0x01)
    4. write the 48-byte record          (cmd 0x06 at offset slot * 0x31)
    5. commit                            (cmd 0x02)

Every packet is 64 bytes:

    byte 0      report id 0x04
    byte 1..2   checksum = sum(packet[3..63]) & 0xffff, little endian
    byte 3      command
    byte 4..    command payload
"""

from __future__ import annotations

import argparse
import datetime
import os
import select
import sys
import time

VID = 0x320F
PID = 0x5055
USAGE_PAGE = 0xFF1C
USAGE = 0x92

REPORT_SIZE = 64
REPORT_ID = 0x04
CONFIG_PAYLOAD_OFFSET = 8
RECORD_SIZE = 48
TIME_OFFSET = 35
TIME_SIZE = 7
SLOT_STRIDE = 0x31

CMD_BEGIN = 0x01
CMD_COMMIT = 0x02
CMD_READ_CONFIG = 0x05
CMD_WRITE_CONFIG = 0x06

DEFAULT_TIMEOUT_MS = 1500

# ---------------------------------------------------------------- enumeration


def _read_text(path: str) -> str:
    try:
        with open(path, "r", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def find_screen_interface(verbose: bool = False) -> str | None:
    """Return /dev/hidrawN for the vendor screen collection (0xFF1C / 0x92).

    Matching is done from sysfs so it works without hidapi: the uevent gives
    bus/vid/pid and the report descriptor is scanned for the usage page/usage
    pair. Over Bluetooth this collection does not exist at all -- the protocol
    needs wired USB.
    """
    import glob

    candidates = []
    for dev_path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        name = os.path.basename(dev_path)
        uevent = _read_text(os.path.join(dev_path, "device", "uevent"))
        fields = dict(
            line.split("=", 1) for line in uevent.splitlines() if "=" in line
        )
        hid_id = fields.get("HID_ID", "")
        # HID_ID looks like 0003:0000320F:00005055 (bus:vid:pid, hex)
        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        try:
            bus, vid, pid = (int(p, 16) for p in parts)
        except ValueError:
            continue
        if (vid, pid) != (VID, PID):
            continue
        descriptor = ""
        try:
            with open(
                os.path.join(dev_path, "device", "report_descriptor"), "rb"
            ) as fh:
                descriptor = fh.read().hex()
        except OSError:
            pass
        # Usage Page (0xFF1C) followed by Usage (0x92) => 061cff0992
        if "061cff0992" in descriptor:
            return f"/dev/{name}"
        candidates.append(f"/dev/{name} (bus={bus})")

    if verbose and candidates:
        print(
            "Found the keyboard but no 0xFF1C/0x92 screen interface:\n  "
            + "\n  ".join(candidates),
            file=sys.stderr,
        )
    return None


# ------------------------------------------------------------------- protocol


def bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def unbcd(value: int) -> int:
    return (value >> 4) * 10 + (value & 0x0F)


def is_time_offset(index: int) -> bool:
    return TIME_OFFSET <= index < TIME_OFFSET + TIME_SIZE


def checksum_packet(packet: bytearray) -> None:
    total = sum(packet[3:REPORT_SIZE]) & 0xFFFF
    packet[1] = total & 0xFF
    packet[2] = (total >> 8) & 0xFF


def build_simple_packet(cmd: int) -> bytearray:
    packet = bytearray(REPORT_SIZE)
    packet[0] = REPORT_ID
    packet[3] = cmd
    checksum_packet(packet)
    return packet


def build_config_packet(
    cmd: int, payload: bytes | None, length: int, offset: int
) -> bytearray:
    packet = bytearray(REPORT_SIZE)
    packet[0] = REPORT_ID
    packet[3] = cmd
    packet[4] = length & 0xFF
    packet[5] = offset & 0xFF
    packet[6] = (offset >> 8) & 0xFF
    packet[7] = 0
    if payload:
        room = REPORT_SIZE - CONFIG_PAYLOAD_OFFSET
        packet[CONFIG_PAYLOAD_OFFSET : CONFIG_PAYLOAD_OFFSET + room] = payload[:room]
    checksum_packet(packet)
    return packet


def slot_offset(slot: int) -> int:
    return slot * SLOT_STRIDE


# ---------------------------------------------------------------- hidraw i/o


class Device:
    def __init__(self, path: str, timeout_ms: int = DEFAULT_TIMEOUT_MS, debug=False):
        self.path = path
        self.timeout = timeout_ms / 1000.0
        self.debug = debug
        self.fd = os.open(path, os.O_RDWR)

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass

    def __enter__(self) -> "Device":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _drain(self) -> None:
        """Drop any stale input reports so responses cannot desync."""
        while select.select([self.fd], [], [], 0)[0]:
            try:
                if not os.read(self.fd, REPORT_SIZE):
                    break
            except OSError:
                break

    def transfer(self, packet: bytearray, expected_cmd: int) -> bytes | None:
        """Send one 64-byte report and return the matching response, if any."""
        self._drain()
        if self.debug:
            print(f"    -> {packet.hex(' ')}")
        os.write(self.fd, bytes(packet))

        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            ready = select.select([self.fd], [], [], remaining)[0]
            if not ready:
                return None
            try:
                data = os.read(self.fd, REPORT_SIZE)
            except OSError:
                return None
            if not data:
                continue
            # hidraw includes the report id; normalise if a backend strips it.
            if data[0] != REPORT_ID:
                data = bytes([REPORT_ID]) + data
            if self.debug:
                print(f"    <- {data.hex(' ')}")
            if len(data) >= 4 and data[3] == expected_cmd:
                return data
            # Not our response (e.g. a keyboard report) -- keep waiting.


def read_record(dev: Device, slot: int) -> bytes:
    record = bytearray(RECORD_SIZE)
    base = slot_offset(slot)
    for pos in range(0, RECORD_SIZE, 4):
        chunk = min(4, RECORD_SIZE - pos)
        packet = build_config_packet(CMD_READ_CONFIG, None, chunk, base + pos)
        response = dev.transfer(packet, CMD_READ_CONFIG)
        if response is None:
            raise RuntimeError(
                f"no response to cmd 0x05 at offset 0x{base + pos:04x}"
            )
        if len(response) >= REPORT_SIZE and bytes(response) == bytes(packet):
            raise RuntimeError(
                "device echoed the request instead of returning a record "
                "(wrong HID collection -- use the 0xFF1C/0x92 screen interface)"
            )
        if len(response) < 4 + chunk:
            raise RuntimeError(
                f"short read at offset 0x{base + pos:04x}: "
                f"{len(response)} bytes, need {4 + chunk}"
            )
        record[pos : pos + chunk] = response[4 : 4 + chunk]
    if not any(record):
        raise RuntimeError("device returned an all-zero record; refusing to write")
    return bytes(record)


def time_bytes(when: datetime.datetime) -> bytes:
    """Pack the host clock into the record's 7 packed-BCD time bytes."""
    weekday = (when.weekday() + 1) % 7  # Sunday=0 .. Saturday=6
    return bytes(
        [
            bcd(when.second),
            bcd(when.minute),
            bcd(when.hour),
            weekday,
            bcd(when.day),
            bcd(when.month),
            bcd(when.year % 100),
        ]
    )


def patch_record(record: bytes, when: datetime.datetime) -> bytes:
    patched = bytearray(record)
    patched[TIME_OFFSET : TIME_OFFSET + TIME_SIZE] = time_bytes(when)
    return bytes(patched)


def verify_only_time_changed(before: bytes, after: bytes) -> None:
    for index in range(RECORD_SIZE):
        if not is_time_offset(index) and before[index] != after[index]:
            raise RuntimeError(
                f"internal safety check failed: offset {index} would change "
                f"({before[index]:02x} -> {after[index]:02x})"
            )


def write_record(dev: Device, record: bytes, slot: int) -> None:
    begin = build_simple_packet(CMD_BEGIN)
    write = build_config_packet(
        CMD_WRITE_CONFIG, record, RECORD_SIZE, slot_offset(slot)
    )
    commit = build_simple_packet(CMD_COMMIT)

    for label, packet, cmd in (
        ("cmd 0x01 begin ", begin, CMD_BEGIN),
        ("cmd 0x06 write ", write, CMD_WRITE_CONFIG),
    ):
        response = dev.transfer(packet, cmd)
        if response is None:
            raise RuntimeError(f"no response to {label.strip()}")
        status = response[7] if len(response) >= 8 else 0
        if status == 0xFF:
            raise RuntimeError(f"{label.strip()} rejected (status 0xff)")
        if status == 0xFE:
            raise RuntimeError(f"{label.strip()} rejected (status 0xfe)")

    time.sleep(0.010)  # the Windows tool sleeps ~10 ms before commit

    response = dev.transfer(commit, CMD_COMMIT)
    if response is None:
        raise RuntimeError("no response to cmd 0x02 commit")
    status = response[7] if len(response) >= 8 else 0
    if status in (0xFF, 0xFE):
        raise RuntimeError(f"cmd 0x02 commit rejected (status 0x{status:02x})")


# ------------------------------------------------------------------- display


def describe(record: bytes) -> str:
    sec, minute, hour = (unbcd(record[35]), unbcd(record[36]), unbcd(record[37]))
    weekday = record[38]
    day, month, year = (unbcd(record[39]), unbcd(record[40]), unbcd(record[41]))
    names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    day_name = names[weekday] if 0 <= weekday <= 6 else f"?({weekday})"
    valid = (
        sec <= 59
        and minute <= 59
        and hour <= 23
        and 1 <= day <= 31
        and 1 <= month <= 12
        and weekday <= 6
    )
    text = (
        f"20{year:02d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{sec:02d} "
        f"({day_name})"
    )
    return text if valid else text + "   [not valid BCD]"


def print_record(record: bytes, label: str) -> None:
    print(f"{label}: {describe(record)}")
    for row in range(0, RECORD_SIZE, 16):
        chunk = record[row : row + 16]
        print(
            f"  {row:02d}: "
            + " ".join(f"{b:02x}" for b in chunk)
            + "   "
            + "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        )


# ---------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync the CIDOO ABM066 LCD clock over USB (wired mode)."
    )
    parser.add_argument(
        "command",
        choices=["list", "read", "dry-run", "set"],
        help="list interfaces | read the record | preview | write the clock",
    )
    parser.add_argument("--slot", type=int, default=0, help="config slot (default 0)")
    parser.add_argument(
        "--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS, help="HID timeout"
    )
    parser.add_argument(
        "--at",
        metavar="YYYY-MM-DDTHH:MM:SS",
        help="use a fixed local time instead of the host clock (testing)",
    )
    parser.add_argument("--device", help="use this /dev/hidrawN directly")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print nothing on success, and exit 0 when the keyboard is not on USB (for timers)",
    )
    parser.add_argument("--debug", action="store_true", help="dump every packet")
    parser.add_argument(
        "--save-template",
        metavar="PATH",
        help="write the record read from the device to PATH before changing it",
    )
    args = parser.parse_args(argv)

    path = args.device or find_screen_interface(verbose=not args.quiet)

    if args.command == "list":
        print("Keyboard interfaces (vendor 0x320f:0x5055):")
        found = False
        for dev in __import__("hid").enumerate(VID, PID):
            print(
                f"  {dev['path'].decode() if isinstance(dev['path'], bytes) else dev['path']}"
                f"  usage_page=0x{dev['usage_page']:04x} usage=0x{dev['usage']:02x}"
                f"  iface={dev.get('interface_number')}"
            )
            found = True
        if not found:
            print("  (none -- the keyboard is not connected over USB)")
        return 0

    if path is None:
        if args.quiet:
            return 0
        print(
            "\nScreen interface 0xFF1C/0x92 not found.\n"
            "This protocol only exists in WIRED USB mode. Bluetooth exposes only\n"
            "standard HID collections (report id 4 there is the mouse), so plug the\n"
            "keyboard in with a USB cable (mode switch to wired/off) and retry.",
            file=sys.stderr,
        )
        return 1

    if args.at:
        when = datetime.datetime.fromisoformat(args.at)
    else:
        when = datetime.datetime.now()

    def say(*parts: object) -> None:
        if not args.quiet:
            print(*parts)

    say(f"Device      : {path}")
    say(f"Host time   : {when.strftime('%Y-%m-%d %H:%M:%S')}")

    with Device(path, args.timeout_ms, args.debug) as dev:
        current = read_record(dev, args.slot)
        if not args.quiet:
            print_record(current, "LCD clock now")

        if args.save_template:
            with open(args.save_template, "wb") as fh:
                fh.write(current)
            say(f"Saved template -> {args.save_template}")

        patched = patch_record(current, when)
        verify_only_time_changed(current, patched)
        if not args.quiet:
            print_record(patched, "Would become ")

        if args.command == "read":
            return 0

        if args.command == "dry-run":
            say("\nDry run: nothing was written.")
            return 0

        write_record(dev, patched, args.slot)
        say("\nClock written.")

        time.sleep(0.3)
        after = read_record(dev, args.slot)
        if not args.quiet:
            print_record(after, "LCD clock now")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)
