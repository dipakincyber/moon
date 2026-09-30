#!/bin/sh
set -eu

version=$(sed -n 's/^Version: //p' debian/package-control)
root="$(pwd)/build/moon-deb-root"
output="$(pwd)/moon-personal_${version}_all.deb"

rm -rf "$root" "$output"
mkdir -p "$root/DEBIAN" "$root/usr/bin" "$root/usr/lib/moon/moon" \
    "$root/usr/share/moon/sounds" "$root/lib/systemd/system" \
    "$root/usr/lib/systemd/user"
cp debian/package-control "$root/DEBIAN/control"
cp debian/postinst debian/prerm debian/postrm "$root/DEBIAN/"
chmod 0755 "$root/DEBIAN/postinst" "$root/DEBIAN/prerm" "$root/DEBIAN/postrm"
cp debian/moon "$root/usr/bin/moon"
chmod 0755 "$root/usr/bin/moon"
cp moon/*.py "$root/usr/lib/moon/moon/"
cp sounds/* "$root/usr/share/moon/sounds/"
cp debian/moon-personal.service "$root/lib/systemd/system/moon-personal.service"
cp debian/moon-personal-user.service "$root/usr/lib/systemd/user/moon-personal-user.service"
dpkg-deb --build --root-owner-group "$root" "$output"
printf '%s\n' "$output"