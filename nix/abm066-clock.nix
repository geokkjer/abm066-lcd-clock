# Home Manager module: keep the CIDOO ABM066 LCD clock in sync.
#
# Mirrors what install.sh sets up:
#   abm066-clock.service  = systemd --user oneshot that pushes the host clock
#   abm066-clock.timer    = fires 1 min after login, then every 6 hours
#
# The keyboard only exposes its vendor screen interface (0xFF1C:0x92) in WIRED
# USB mode. On Bluetooth or 2.4 GHz the script finds nothing and exits 0
# without writing, so the timer stays quiet.
#
# Each successful run rewrites one 48-byte config record in the keyboard flash,
# which is why the interval is 6 hours rather than minutes.
#
# Usage:
#   imports = [ ./hardware/abm066-clock.nix ];
#
# Keep abm066_clock.py at the repo root, one level up from this file.

{ pkgs, ... }:

let
  abm066-clock = pkgs.writeShellApplication {
    name = "abm066-clock";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      exec python3 ${../abm066_clock.py} "$@"
    '';
  };
in
{
  home.packages = [ abm066-clock ];

  systemd.user.services.abm066-clock = {
    Unit.Description = "Sync the CIDOO ABM066 LCD clock over USB";
    Service = {
      Type = "oneshot";
      ExecStart = "${abm066-clock}/bin/abm066-clock set --quiet";
    };
  };

  systemd.user.timers.abm066-clock = {
    Unit.Description = "Periodically sync the CIDOO ABM066 LCD clock";
    Timer = {
      OnBootSec = "1min";
      OnUnitActiveSec = "6h";
      AccuracySec = "1min";
      Unit = "abm066-clock.service";
    };
    Install.WantedBy = [ "timers.target" ];
  };

  # The keyboard's hidraw node is normally root:users 0660. If your user is not
  # in `users`, grant access with a udev rule instead:
  #
  #   services.udev.extraRules = ''
  #     SUBSYSTEM=="hidraw", ATTRS{idVendor}=="320f", ATTRS{idProduct}=="5055", \
  #       MODE="0660", GROUP="users"
  #   '';
  #
  # To sync the moment you plug the keyboard in instead of waiting for the
  # timer (the device must belong to your seat for SYSTEMD_USER_WANTS):
  #
  #   services.udev.extraRules = ''
  #     ACTION=="add", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="320f", \
  #       ATTRS{idProduct}=="5055", TAG+="systemd", \
  #       ENV{SYSTEMD_USER_WANTS}+="abm066-clock.service"
  #   '';
}
