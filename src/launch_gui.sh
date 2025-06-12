#!/usr/bin/env bash

# Script Name: Portable Data Network + Reverse Wireless GUI Launcher
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Jacy Kincade (1ndevelopment@protonmail.com)
#
# Creates a virtual environment, installs PyQt5, and launches a GUI script.
# This script is designed to be run as root (e.g., using sudo) to ensure it has
# the necessary permissions to create a virtual environment and run GUI applications.
# It also handles cleanup of the virtual environment on exit, whether the script
# exits normally, due to an error, or is interrupted (e.g., Ctrl+C).

# Exit on error, treat unset variables as errors, and handle pipe failures
set -e
# set -u # Uncomment if you are sure all variables are always set
set -o pipefail

# --- Configuration ---
_SCRIPT_PATH="$(realpath "$0")"
_WORKSPACE="$(dirname "$_SCRIPT_PATH")"
VENV_DIR="$_WORKSPACE/venv"
ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"

UI_SCRIPT="$_WORKSPACE/ui.py"

PROXY_URL="http://192.168.49.1:8000" # Set to "" or remove --proxy arg if not needed

# --- Root Check ---
if [ "$(id -u)" -ne 0 ]; then
  echo "Error: This script must be run as root (e.g., using sudo)." >&2
  exit 1
fi

# --- XDG Runtime Directory for GUI as root ---
# Systemd typically creates /run/user/$UID. For root (UID 0), this is /run/user/0.
# If it doesn't exist, create a fallback.
if [ -d "/run/user/0" ]; then
    export XDG_RUNTIME_DIR="/run/user/0"
else
    export XDG_RUNTIME_DIR="/tmp/runtime-root"
    # Ensure the fallback directory exists and has correct permissions
    if [ ! -d "$XDG_RUNTIME_DIR" ]; then
        echo "Creating XDG_RUNTIME_DIR at $XDG_RUNTIME_DIR..."
        mkdir -p "$XDG_RUNTIME_DIR"
    fi
    chmod 0700 "$XDG_RUNTIME_DIR"
    # chown root:root "$XDG_RUNTIME_DIR" # mkdir -p as root should set this correctly
fi
echo "Using XDG_RUNTIME_DIR: $XDG_RUNTIME_DIR"


# --- Cleanup Function ---
# This function will be called on EXIT signal (normal exit, error, or Ctrl+C)
cleanup_on_exit() {
  echo # Newline for cleaner exit messages
  # Deactivate virtual environment if it was activated and deactivate command exists
  if command -v deactivate &>/dev/null && [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "Deactivating virtual environment..."
    deactivate
  fi

  # Remove the virtual environment directory if it exists
  if [ -d "$VENV_DIR" ]; then
    echo "Removing virtual environment '$VENV_DIR'..."
    # No sudo needed as we are already root
    rm -rf "$VENV_DIR"
    echo "Virtual environment removed."
  # else
    # echo "Virtual environment directory '$VENV_DIR' not found for removal (already cleaned or never created)."
  fi
}
# Register the cleanup function to run on script exit
trap cleanup_on_exit EXIT

# --- Prerequisite Checks ---
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 command not found. Please install Python 3." >&2
    exit 1
fi

if ! python3 -m venv -h &>/dev/null; then
    echo "Error: python3-venv module not found. Please install it." >&2
    echo "On Debian/Ubuntu: sudo apt update && sudo apt install python3-venv" >&2
    exit 1
fi

# --- Virtual Environment Setup ---
if [ ! -f "$ACTIVATE_SCRIPT" ]; then
  echo "Virtual environment not found or incomplete. Setting up..."

  # Clean up any previous potentially broken state
  if [ -d "$VENV_DIR" ]; then
      echo "Removing existing (potentially broken) venv directory: $VENV_DIR"
      rm -rf "$VENV_DIR"
  fi

  echo "Creating virtual environment in '$VENV_DIR'..."
  python3 -m venv "$VENV_DIR" # set -e handles failure

  echo "Activating new virtual environment for package installation..."
  # Source directly into current shell. This is needed for pip to use the venv.
  # The curly braces ensure that if source fails, set -e will trigger.
  # shellcheck source=/dev/null
  source "$ACTIVATE_SCRIPT"

  echo "Installing PyQt5 (this may take a moment)..."
  # Ensure pip is available in the venv (it should be)
  if ! command -v pip3 &>/dev/null; then
      echo "Error: pip3 not found in the virtual environment. This is unexpected." >&2
      echo "The python3-venv package might be incomplete or corrupted." >&2
      exit 1
  fi

  if [ -n "$PROXY_URL" ]; then
    echo "Using proxy: $PROXY_URL"
    pip install --upgrade --proxy "$PROXY_URL" pip >/dev/null 2>&1
    pip3 install --proxy "$PROXY_URL" PyQt5 >/dev/null 2>&1
  else
    echo "No proxy configured. Installing directly."
    pip install --upgrade pip >/dev/null 2>&1
    pip3 install PyQt5 >/dev/null 2>&1
  fi
  # set -e handles pip install failure

  echo "Virtual environment setup complete."
  # Venv is now active for the rest of the script
else
  echo "Activating existing virtual environment..."
  # shellcheck source=/dev/null
  . "$ACTIVATE_SCRIPT" # set -e handles failure
  echo "Virtual environment activated."
fi

# --- Check for Python UI script ---
if [ ! -f "$UI_SCRIPT" ]; then
    echo "Error: Python UI script '$UI_SCRIPT' not found." >&2
    exit 1
fi

# --- Execute GUI ---
echo "Launching GUI: $UI_SCRIPT"
python3 "$UI_SCRIPT"
# The exit status of python3 will become the script's exit status due to set -e
# (unless python3 ui.py exits 0, then trap runs and script exits 0)

echo "GUI exited."
# The trap 'cleanup_on_exit' will run automatically upon script exit.
# No need for an explicit call to a removal function here.