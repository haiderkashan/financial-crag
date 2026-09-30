/**
 * Verification Test Script for Sub-Phase 4.2: useAgentStream Hook
 *
 * Verifies:
 * 1. Initial state invariant (status === "idle", activeNode === null, elapsedMs === 0).
 * 2. submitQuery state transition to "streaming".
 * 3. Step accumulation and activeNode updates during execution.
 * 4. Final transition to "complete", activeNode reset, elapsedMs calculation, generation capture.
 * 5. cancelQuery() and resetState() lifecycle methods.
 */

const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

// Minimal reproduction of useAgentStream state logic for CLI execution
class AgentStreamManager {
  constructor(apiBaseUrl, cookie) {
    this.apiBaseUrl = apiBaseUrl;
    this.cookie = cookie;
    this.state = {
      status: "idle",
      steps: [],
      activeNode: null,
      generation: "",
      error: null,
      elapsedMs: 0,
    };
    this.controller = null;
    this.timer = null;
    this.startTime = 0;
    this.stateTransitions = [];
  }

  _recordTransition(action, details = {}) {
    this.stateTransitions.push({
      action,
      status: this.state.status,
      activeNode: this.state.activeNode,
      stepsCount: this.state.steps.length,
      genLength: this.state.generation.length,
      elapsedMs: this.state.elapsedMs,
      ...details,
    });
  }

  cancelQuery() {
    if (this.controller) {
      this.controller.abort();
      this.controller = null;
    }
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.state.status === "streaming") {
      this.state.status = "idle";
    }
    this.state.activeNode = null;
    this._recordTransition("cancelQuery");
  }

  resetState() {
    if (this.controller) {
      this.controller.abort();
      this.controller = null;
    }
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.state = {
      status: "idle",
      steps: [],
      activeNode: null,
      generation: "",
      error: null,
      elapsedMs: 0,
    };
    this._recordTransition("resetState");
  }

  async submitQuery(payload) {
    if (this.controller) {
      this.controller.abort();
    }
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }

    this.controller = new AbortController();
    this.startTime = Date.now();

    this.state.status = "streaming";
    this.state.steps = [];
    this.state.activeNode = null;
    this.state.generation = "";
    this.state.error = null;
    this.state.elapsedMs = 0;
    this._recordTransition("submitQuery:start");

    this.timer = setInterval(() => {
      this.state.elapsedMs = Date.now() - this.startTime;
    }, 100);

    try {
      const response = await fetch(`${this.apiBaseUrl}/agent/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: this.cookie,
        },
        body: JSON.stringify(payload),
        signal: this.controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      const processBlock = (block) => {
        const lines = block.split("\n");
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data:")) {
            const jsonStr = trimmed.slice(5).trim();
            if (jsonStr) {
              try {
                const event = JSON.parse(jsonStr);

                if (event.type === "step") {
                  this.state.steps.push(event);
                  if (event.node) {
                    this.state.activeNode = event.node;
                  }
                  this._recordTransition("event:step", { node: event.node, message: event.message });
                  console.log(`  [HOOK EVENT] status="streaming" | activeNode="${event.node}" | steps=${this.state.steps.length}`);
                  console.log(`               -> ${event.message}`);
                } else if (event.type === "generation") {
                  this.state.generation = event.content || "";
                  this._recordTransition("event:generation", { length: this.state.generation.length });
                  console.log(`  [HOOK EVENT] status="streaming" | generation received (${this.state.generation.length} chars)`);
                } else if (event.type === "done") {
                  if (this.timer) {
                    clearInterval(this.timer);
                    this.timer = null;
                  }
                  this.state.elapsedMs = Date.now() - this.startTime;
                  this.state.status = "complete";
                  this.state.activeNode = null;
                  this._recordTransition("event:done");
                  console.log(`  [HOOK EVENT] status="complete" | activeNode=null | elapsed=${(this.state.elapsedMs / 1000).toFixed(2)}s`);
                } else if (event.type === "error") {
                  if (this.timer) {
                    clearInterval(this.timer);
                    this.timer = null;
                  }
                  this.state.elapsedMs = Date.now() - this.startTime;
                  this.state.status = "error";
                  this.state.error = event.message || "Unknown error";
                  this.state.activeNode = null;
                  this._recordTransition("event:error", { error: this.state.error });
                }
              } catch (e) {
                console.warn("Parse error:", e);
              }
            }
          }
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          processBlock(block);
        }
      }

      const rest = buffer + decoder.decode();
      if (rest.trim()) {
        processBlock(rest);
      }
    } catch (err) {
      if (this.controller?.signal.aborted) {
        return;
      }
      if (this.timer) {
        clearInterval(this.timer);
        this.timer = null;
      }
      this.state.elapsedMs = Date.now() - this.startTime;
      this.state.status = "error";
      this.state.error = err.message || String(err);
      this.state.activeNode = null;
      this._recordTransition("catch:error", { error: this.state.error });
    }
  }
}

async function runTest() {
  console.log("===============================================================");
  console.log("SUB-PHASE 4.2: useAgentStream HOOK STATE MACHINE VERIFICATION");
  console.log("===============================================================");

  // 1. Establish session
  console.log("\n[1] Authenticating session...");
  const reqRes = await fetch(`${API_BASE_URL}/auth/request-magic-link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "lead.analyst@hedgefund.com" }),
  });
  const reqData = await reqRes.json();
  const verifyRes = await fetch(`${API_BASE_URL}/auth/verify-token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: reqData.dev_token }),
  });
  const cookie = verifyRes.headers.get("set-cookie") || "";
  console.log("    Session established (cookie acquired).");

  // 2. Initialize manager
  const hook = new AgentStreamManager(API_BASE_URL, cookie);

  // Assertion 1: Initial state
  console.log("\n[2] Checking Initial State Invariants:");
  console.log(`    - status:     "${hook.state.status}" (expected: "idle")`);
  console.log(`    - steps:      [${hook.state.steps.length}] (expected: 0)`);
  console.log(`    - activeNode: ${hook.state.activeNode} (expected: null)`);
  console.log(`    - generation: "${hook.state.generation}" (expected: "")`);
  console.log(`    - elapsedMs:  ${hook.state.elapsedMs} (expected: 0)`);

  if (hook.state.status !== "idle" || hook.state.steps.length !== 0 || hook.state.activeNode !== null) {
    throw new Error("Assertion failed: Invalid initial state.");
  }
  console.log("    => Initial state invariants passed ✓");

  // 3. Trigger submitQuery
  console.log("\n[3] Calling submitQuery({ question, ticker: 'AAPL', fiscal_year: 2023 })...");
  const queryPromise = hook.submitQuery({
    question: "What were Apple's net sales in 2023?",
    ticker: "AAPL",
    fiscal_year: 2023,
  });

  // Verify transition to streaming
  console.log(`    - Immediate status: "${hook.state.status}" (expected: "streaming")`);
  if (hook.state.status !== "streaming") {
    throw new Error(`Assertion failed: Expected status "streaming", got "${hook.state.status}"`);
  }

  // Await completion
  await queryPromise;

  // Assertion 4: Final state invariants
  console.log("\n[4] Checking Final State Invariants:");
  console.log(`    - status:      "${hook.state.status}" (expected: "complete")`);
  console.log(`    - steps:       ${hook.state.steps.length} events accumulated`);
  console.log(`    - activeNode:  ${hook.state.activeNode} (expected: null upon completion)`);
  console.log(`    - generation:  ${hook.state.generation.length} characters`);
  console.log(`    - elapsedMs:   ${hook.state.elapsedMs}ms (${(hook.state.elapsedMs / 1000).toFixed(2)}s)`);
  console.log(`    - error:       ${hook.state.error} (expected: null)`);

  if (hook.state.status !== "complete") {
    throw new Error(`Assertion failed: Expected final status "complete", got "${hook.state.status}"`);
  }
  if (hook.state.steps.length === 0) {
    throw new Error("Assertion failed: No steps were captured in state.steps");
  }
  if (!hook.state.generation || hook.state.generation.length === 0) {
    throw new Error("Assertion failed: state.generation is empty");
  }
  if (hook.state.activeNode !== null) {
    throw new Error(`Assertion failed: activeNode should reset to null, got "${hook.state.activeNode}"`);
  }
  if (hook.state.elapsedMs <= 0) {
    throw new Error("Assertion failed: elapsedMs should be > 0");
  }
  console.log("    => Final state invariants passed ✓");

  // 5. Test resetState()
  console.log("\n[5] Testing resetState()...");
  hook.resetState();
  console.log(`    - status after reset:     "${hook.state.status}" (expected: "idle")`);
  console.log(`    - steps after reset:      ${hook.state.steps.length} (expected: 0)`);
  console.log(`    - generation after reset: "${hook.state.generation}" (expected: "")`);
  console.log(`    - elapsedMs after reset:  ${hook.state.elapsedMs} (expected: 0)`);

  if (hook.state.status !== "idle" || hook.state.steps.length !== 0 || hook.state.generation !== "") {
    throw new Error("Assertion failed: resetState did not restore initial state.");
  }
  console.log("    => resetState() verified ✓");

  // 6. Test cancelQuery()
  console.log("\n[6] Testing cancelQuery()...");
  const cancelPromise = hook.submitQuery({
    question: "What were Apple's net sales in 2023?",
    ticker: "AAPL",
    fiscal_year: 2023,
  });
  console.log(`    - status immediately after submit: "${hook.state.status}"`);
  hook.cancelQuery();
  console.log(`    - status immediately after cancel: "${hook.state.status}" (expected: "idle")`);
  if (hook.state.status !== "idle") {
    throw new Error(`Assertion failed: Expected "idle" after cancel, got "${hook.state.status}"`);
  }
  await cancelPromise;
  console.log("    => cancelQuery() verified ✓");

  console.log("\n===============================================================");
  console.log("ALL useAgentStream HOOK VERIFICATION ASSERTIONS PASSED ✓");
  console.log("State Transitions Verified: idle -> streaming -> complete -> idle");
  console.log("===============================================================");
}

runTest().catch((err) => {
  console.error("\n[!] VERIFICATION FAILED:", err);
  process.exit(1);
});
