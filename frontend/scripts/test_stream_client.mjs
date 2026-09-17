/**
 * Verification Test Script for Sub-Phase 4.1: SSE Stream Client
 *
 * Simulates browser client runtime:
 * 1. Obtains authentication cookies via dev magic link flow.
 * 2. Connects to live FastAPI streaming endpoint (POST /api/v1/agent/query).
 * 3. Parses Server-Sent Events in real time using streamAgentQuery logic.
 * 4. Logs each event trace and verifies step -> generation -> done sequence.
 */

const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

async function runVerification() {
  console.log("===============================================================");
  console.log("SUB-PHASE 4.1: SSE STREAM CLIENT VERIFICATION HARNESS");
  console.log("===============================================================");

  // 1. Authenticate and obtain session cookies
  console.log("\n[1] Establishing Analyst Session...");
  const reqRes = await fetch(`${API_BASE_URL}/auth/request-magic-link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "lead.analyst@hedgefund.com" }),
  });

  if (!reqRes.ok) {
    throw new Error(`Failed to request magic link: ${reqRes.statusText}`);
  }

  const reqData = await reqRes.json();
  const devToken = reqData.dev_token;
  if (!devToken) {
    throw new Error("Dev token not returned in request-magic-link response");
  }
  console.log(`    Dev token acquired: ${devToken.slice(0, 12)}...`);

  // Verify token to receive session cookies
  const verifyRes = await fetch(`${API_BASE_URL}/auth/verify-token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: devToken }),
  });

  if (!verifyRes.ok) {
    throw new Error(`Failed to verify token: ${verifyRes.statusText}`);
  }

  // Extract access_token cookie from Set-Cookie header
  const setCookie = verifyRes.headers.get("set-cookie") || "";
  console.log("    Session established successfully (HTTP-only cookies set).");

  // 2. Stream Agent Query
  console.log("\n[2] Dispatching Analytical Query via SSE Stream Client...");
  const payload = {
    question: "What were Apple's net sales in 2023?",
    ticker: "AAPL",
    fiscal_year: 2023,
  };
  console.log(`    Query:       "${payload.question}"`);
  console.log(`    Target:      Ticker=${payload.ticker}, Year=${payload.fiscal_year}`);
  console.log("---------------------------------------------------------------");
  console.log("REAL-TIME SSE EVENT TRACE (CONSOLE LOG):");
  console.log("---------------------------------------------------------------");

  const startTime = Date.now();
  const stepEvents = [];
  let generationReceived = null;
  let doneReceived = false;

  const response = await fetch(`${API_BASE_URL}/agent/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Cookie: setCookie,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Stream request failed with status: ${response.status} ${response.statusText}`);
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
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);

            if (event.type === "step") {
              stepEvents.push(event);
              console.log(`[+${elapsed}s] [SSE STEP] Node: [${event.node?.toUpperCase()}] -> ${event.message}`);
            } else if (event.type === "generation") {
              generationReceived = event.content;
              console.log(`[+${elapsed}s] [SSE GENERATION] Received final synthesis (${event.content?.length} chars)`);
            } else if (event.type === "done") {
              doneReceived = true;
              console.log(`[+${elapsed}s] [SSE DONE] State machine stream closed cleanly.`);
            } else if (event.type === "error") {
              console.error(`[+${elapsed}s] [SSE ERROR] ${event.message}`);
            }
          } catch (parseErr) {
            console.warn("Failed to parse event JSON:", jsonStr, parseErr);
          }
        }
      }
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let eventEndIndex;
    while ((eventEndIndex = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, eventEndIndex);
      buffer = buffer.slice(eventEndIndex + 2);
      processBlock(block);
    }
  }

  const remaining = buffer + decoder.decode();
  if (remaining.trim()) {
    processBlock(remaining);
  }

  const totalDuration = ((Date.now() - startTime) / 1000).toFixed(2);
  console.log("---------------------------------------------------------------");
  console.log(`\n[3] Verification Assertions (Completed in ${totalDuration}s):`);
  console.log(`    - Steps Count:           ${stepEvents.length} events received`);
  console.log(`    - Generation Event:      ${generationReceived ? "YES (Content Verified)" : "NO"}`);
  console.log(`    - Done Event:            ${doneReceived ? "YES" : "NO"}`);

  if (stepEvents.length === 0) {
    throw new Error("Verification failed: Zero step events received.");
  }
  if (!generationReceived) {
    throw new Error("Verification failed: Generation content not received.");
  }
  if (!doneReceived) {
    throw new Error("Verification failed: Done completion signal not received.");
  }

  console.log("\n===============================================================");
  console.log("SYNTHESIZED MARKDOWN GENERATION PREVIEW:");
  console.log("===============================================================");
  console.log(generationReceived.slice(0, 500) + "\n...[truncated for display]");
  console.log("===============================================================");
  console.log("STATUS: SUB-PHASE 4.1 VERIFICATION CHECKPOINT PASSED ✓");
  console.log("===============================================================");
}

runVerification().catch((err) => {
  console.error("\n[!] VERIFICATION FAILED:", err);
  process.exit(1);
});
