#!/bin/bash
# ================================================================
# B!tches Be Tripping — Add Blog Post
# ================================================================
# Usage:
#   ./add_post.sh "GOOGLE_DOC_ID" "Katie"
#   ./add_post.sh "GOOGLE_DOC_ID" "Katie" --date 2026-05-23 --categories "Destinations,Must Do"
#
# First run: sets up a virtual environment and installs dependencies.
# Subsequent runs: skips setup and goes straight to adding the post.
# ================================================================

set -e  # Exit immediately if any command fails

# Directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# ── Step 1: Create virtual environment if it doesn't exist ──
if [ ! -d "$VENV_DIR" ]; then
  echo "Setting up virtual environment for the first time..."
  python3 -m venv "$VENV_DIR"
  echo "Virtual environment created."
fi

# ── Step 2: Activate virtual environment ──
source "$VENV_DIR/bin/activate"

# ── Step 3: Install dependencies if not already installed ──
if ! python3 -c "import googleapiclient" &>/dev/null; then
  echo "Installing dependencies..."
  pip install --quiet \
    google-auth-oauthlib \
    google-auth-httplib2 \
    google-api-python-client
  echo "Dependencies installed."
fi

# ── Step 4: Run the script, passing all arguments through ──
echo ""
python3 "$SCRIPT_DIR/add_post.py" "$@"