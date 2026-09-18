#!/usr/bin/env bash
# Thin wrapper — canonical script lives in HomeLab-AI-Stack on PopOS.
exec "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../../HomeLab-AI-Stack/scripts/release_popos_gpu_for_local.sh" "$@"
