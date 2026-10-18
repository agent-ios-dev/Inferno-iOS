#!/bin/bash
# Required by Inferno's USB transport. Static iPhoneOS objects only.
set -euo pipefail
prefix="${PREFIX:?Set PREFIX to the iOS dependency prefix}"
if [[ -f "$prefix/lib/liblz4.a" && -f "$prefix/lib/pkgconfig/liblz4.pc" ]]; then exit 0; fi
git init .deps-lz4
git -C .deps-lz4 remote add origin https://github.com/lz4/lz4.git
git -C .deps-lz4 fetch --depth 1 origin ebb370ca83af193212df4dcbadcc5d87bc0de2f0
git -C .deps-lz4 checkout --detach FETCH_HEAD
sdk="$(xcrun --sdk iphoneos --show-sdk-path)"
mkdir -p .deps-lz4/objects "$prefix/lib/pkgconfig" "$prefix/include"
for name in lz4 lz4hc lz4frame xxhash; do
  xcrun --sdk iphoneos clang -arch arm64 -isysroot "$sdk" -mios-version-min=16.0 -fPIC -O2 \
    -c ".deps-lz4/lib/$name.c" -o ".deps-lz4/objects/$name.o"
done
xcrun --sdk iphoneos ar rcs "$prefix/lib/liblz4.a" .deps-lz4/objects/*.o
cp .deps-lz4/lib/*.h "$prefix/include/"
cat > "$prefix/lib/pkgconfig/liblz4.pc" <<EOF
prefix=$prefix
libdir=\${prefix}/lib
includedir=\${prefix}/include
Name: lz4
Description: LZ4 compression library (static iPhoneOS)
Version: 1.10.0
Libs: -L\${libdir} -llz4
Cflags: -I\${includedir}
EOF
