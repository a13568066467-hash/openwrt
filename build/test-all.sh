#!/bin/bash
# Run every test that does not need a router or a built firmware.
#
#   wsl.exe -d Ubuntu-22.04 -- bash build/test-all.sh
#
# Covers the ucode agent (against the same interpreter OpenWrt 25.12 ships),
# the router-side shell scripts, and the Go cloud service.
set -u

PROJECT="/mnt/d/Users/Documents/project/openwrt"
FAIL=0

banner() { echo; echo "########## $1 ##########"; echo; }

banner "router agent (ucode)"
if bash "$PROJECT/build/test-agent.sh" 2>&1 | tee /tmp/nds-agent-test.log | tail -8 | grep -q AGENT_TESTS_PASSED; then
  echo "  agent tests passed"
else
  echo "  agent tests FAILED"; FAIL=1
fi

banner "router scripts (shell)"
bash "$PROJECT/build/test-scripts.sh" 2>&1 || FAIL=1

banner "cloud service (go)"
if command -v go >/dev/null 2>&1; then
  (cd "$PROJECT/cloud" && go test ./... 2>&1) || FAIL=1
else
  echo "  go is not installed in WSL; run 'go test ./...' in cloud/ on Windows instead"
fi

banner "result"
if [ "$FAIL" = 0 ]; then echo "ALL_TESTS_PASSED"; else echo "SOME_TESTS_FAILED"; fi
exit $FAIL
