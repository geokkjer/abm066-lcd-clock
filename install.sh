#!/usr/bin/env bash
# Install abm066-lcd-clock as a systemd user service + timer.
#
#   ./install.sh            install and print the enable command
#   ./install.sh --enable   install, then enable and start the timer now
#
# Installs:
#   ~/.local/bin/abm066-clock
#   ~/.config/systemd/user/abm066-clock.{service,timer}
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

enable=0
[[ "${1:-}" == "--enable" ]] && enable=1

install -d "$bin_dir" "$unit_dir"
install -m 755 "$here/abm066_clock.py" "$bin_dir/abm066-clock"
install -m 644 "$here/systemd/abm066-clock.service" "$unit_dir/"
install -m 644 "$here/systemd/abm066-clock.timer" "$unit_dir/"

systemctl --user daemon-reload

echo "Installed:"
echo "  $bin_dir/abm066-clock"
echo "  $unit_dir/abm066-clock.service"
echo "  $unit_dir/abm066-clock.timer"
echo

if (( enable )); then
    systemctl --user enable --now abm066-clock.timer
    echo "Timer enabled. Next runs:"
    systemctl --user list-timers abm066-clock.timer --no-pager || true
else
    echo "Enable it with:"
    echo "  systemctl --user enable --now abm066-clock.timer"
fi

echo
echo "Check it works right now (needs the keyboard in wired USB mode):"
echo "  $bin_dir/abm066-clock read"
