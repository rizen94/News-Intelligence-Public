#!/usr/bin/env bash
exec "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../../HomeLab-AI-Stack/scripts/resume_popos_gpu_after_local.sh" "$@"
