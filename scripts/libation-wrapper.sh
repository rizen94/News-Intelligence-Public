#!/usr/bin/env bash
# libation-wrapper.sh - Wrapper for Libation CLI with TLS fix
# 
# Problem: Mono's default TLS provider in the Libation Snap fails certificate 
# validation when communicating with Audible's API. This happens because Mono's
# built-in certificate store doesn't have access to the system CA certificates
# within snap confinement.
#
# Solution: Set MONO_TLS_PROVIDER=openssl to force Mono to use the system's
# OpenSSL library (which has proper access to /etc/ssl/certs) instead of its
# internal TLS implementation.

set -euo pipefail

export MONO_TLS_PROVIDER=openssl
LIBATION_CLI="/snap/libation/current/usr/lib/libation/LibationCli"

usage() {
    cat << 'EOF'
Libation Wrapper — Mono TLS Fix + Convenience Commands

Usage: ./libation-wrapper.sh <command> [options]

Commands:
  help              Show this help message
  version           Show Libation CLI version
  login             Login via browser (open URL, paste callback)
  list-accounts     List configured Audible accounts and their status
  scan              Scan library for new/unscanned books
  liberate-all      Download/decrypt all un-liberated titles
  liberate <ASIN>   Download a specific book by ASIN
  set-status        Update download status to match actual files
  convert <mp4>     Convert mp4 to mp3
  export [--xlsx|--csv|--json] [path]  Export library metadata
  search <query>    Search your Audible library

Examples:
  ./libation-wrapper.sh login
  ./libation-wrapper.sh scan account=us
  ./libation-wrapper.sh liberate-all --limit-mb=10240
  ./libation-wrapper.sh set-status -d

Note: MONO_TLS_PROVIDER=openssl is automatically set to fix SSL certificate
verification errors when communicating with Audible's API.
EOF
}

# Dispatch
case "${1:-help}" in
    help|--help|-h)
        usage
        ;;
    version)
        exec $LIBATION_CLI version 2>&1
        ;;
    login)
        echo "Opening browser for Audible authentication..."
        echo "When prompted, copy the callback URL from your browser and paste it here."
        exec $LIBATION_CLI login-external 2>&1
        ;;
    list-accounts)
        exec $LIBATION_CLI list-accounts 2>&1
        ;;
    scan)
        shift
        echo "Scanning library..."
        exec $LIBATION_CLI scan "$@" 2>&1
        ;;
    liberate-all)
        shift
        echo "Liberating all un-liberated books..."
        exec $LIBATION_CLI liberate "$@" 2>&1
        ;;
    liberate)
        shift
        echo "Liberating specified book(s):"
        for asin in "$@"; do
            echo "  - $asin"
        done
        exec $LIBATION_CLI liberate "$@" 2>&1
        ;;
    set-status)
        shift
        echo "Updating download status..."
        exec $LIBATION_CLI set-status "$@" 2>&1
        ;;
    convert)
        shift
        echo "Converting audio files..."
        exec $LIBATION_CLI convert "$@" 2>&1
        ;;
    export)
        shift
        exec $LIBATION_CLI export "$@" 2>&1
        ;;
    search)
        shift
        echo "Searching library for: $*"
        exec $LIBATION_CLI search "$@" 2>&1
        ;;
    *)
        # Pass through any other commands directly
        exec $LIBATION_CLI "$@" 2>&1
        ;;
esac
