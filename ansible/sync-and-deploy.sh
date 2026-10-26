#!/usr/bin/env bash
#
# Permanent fix for "the master's ansible folder is stale".
#
# Instead of hand-copying the ansible/ directory to the master with scp, this
# script clones/pulls the repo on the master and runs playbooks straight from
# the freshly-pulled copy. The master can therefore never drift from git.
#
# Usage (on the ansible master):
#   ./sync-and-deploy.sh <branch> <limit> [extra ansible-playbook args...]
#
# Examples:
#   ./sync-and-deploy.sh dev frontend
#   ./sync-and-deploy.sh dev backend --extra-vars "serpapi_key=XXXX"
#   ./sync-and-deploy.sh dev all
#
set -euo pipefail

REPO_URL="https://github.com/gswack/buybot.git"
CLONE_DIR="$HOME/buybot"
BRANCH="${1:-dev}"
LIMIT="${2:-all}"
shift 2 || true   # remaining args passed through to ansible-playbook

# 1. Clone the repo if missing, otherwise hard-sync it to the remote branch.
if [ ! -d "$CLONE_DIR/.git" ]; then
  echo ">> Cloning $REPO_URL into $CLONE_DIR"
  git clone "$REPO_URL" "$CLONE_DIR"
fi

echo ">> Syncing $CLONE_DIR to origin/$BRANCH"
git -C "$CLONE_DIR" fetch origin
git -C "$CLONE_DIR" checkout "$BRANCH"
git -C "$CLONE_DIR" reset --hard "origin/$BRANCH"

# 2. Run the playbook from the repo's ansible/ folder (always current).
ANSIBLE_DIR="$CLONE_DIR/ansible"
echo ">> Running deploy from $ANSIBLE_DIR (limit=$LIMIT)"
cd "$ANSIBLE_DIR"
ansible-playbook -i inventory.ini playbooks/deploy.yaml --limit "$LIMIT" "$@"
