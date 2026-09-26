#!/bin/sh
# Compiles Salt's Foundation-only core with its checks.
# The iOS app target does not include this runner.
set -eu
cd "$(dirname "$0")"

if command -v swiftc >/dev/null 2>&1; then
    compiler=swiftc
elif command -v xcrun >/dev/null 2>&1; then
    compiler="xcrun swiftc"
else
    echo "swiftc not found" >&2
    exit 1
fi

files=$(find Salt/Core -name '*.swift' | sort)
# shellcheck disable=SC2086
$compiler -swift-version 5 -o /tmp/salt-core-tests $files SaltTests/main.swift
/tmp/salt-core-tests
