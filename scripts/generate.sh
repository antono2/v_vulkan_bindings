#!/usr/bin/env sh
# Compatibility entry point for callers of the former shell launcher.
exec v run "$(dirname "$0")/generate.vsh" "$@"
