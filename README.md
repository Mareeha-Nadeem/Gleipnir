# Gleipnir
This is an AI agent that find flaky tests in a codebase, and tells why they fail randomly, and fixes them.  For this, the test suite will be run under varied conditions to statistically confirm which tests are truly flaky, then dispatches subagents to diagnose the root cause Then it will suggest fixes.
