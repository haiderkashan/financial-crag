"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { requestMagicLink, isLoading, error, clearError } = useAuth();
  const [email, setEmail] = useState("");
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    clearError();
    try {
      const msg = await requestMagicLink(email.trim());
      setSubmittedEmail(email.trim());
      setFeedbackMessage(msg);
    } catch {
      // Error is captured in context
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-[#F7F7F5] text-[#111111]">
      {/* Top Header / Status Ticker */}
      <header className="border-b border-[#111111] px-6 py-3 flex flex-wrap items-center justify-between font-mono text-xs tracking-wider uppercase bg-[#F7F7F5]">
        <div className="flex items-center gap-4">
          <Link href="/" className="bg-[#111111] text-[#F7F7F5] px-2 py-0.5 font-bold hover:bg-[#E5A823] hover:text-black transition-colors">
            CRAG-SEC
          </Link>
          <span>GATEWAY: ANALYST_AUTHENTICATION</span>
          <span className="hidden sm:inline text-neutral-400">|</span>
          <span className="hidden sm:inline text-neutral-600">ZERO_KNOWLEDGE_PROTOCOL</span>
        </div>
        <div>
          <span className="text-[#E5A823] font-bold">[ READY ]</span>
        </div>
      </header>

      {/* Center Container */}
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="max-w-xl w-full border border-[#111111] bg-white p-8 md:p-10 rounded-none shadow-none">
          <div className="font-sans text-xs tracking-widest uppercase text-neutral-500 mb-3 pb-2 border-b border-[#111111]">
            SEC Intelligence Access Protocol
          </div>

          <h1 className="font-sans text-2xl md:text-3xl font-black uppercase tracking-tight text-[#111111] mb-4">
            Analyst Authentication
          </h1>

          <p className="font-serif text-base text-[#333333] leading-relaxed mb-6">
            Access to SEC 10-K financial calculations and Corrective-RAG intelligence is restricted to verified analysts. Enter your institutional email to dispatch a single-use verification token.
          </p>

          {submittedEmail ? (
            <div className="border border-[#111111] bg-[#F7F7F5] p-6 font-mono text-xs rounded-none">
              <div className="text-[#111111] font-bold uppercase tracking-wider mb-2 flex items-center justify-between">
                <span>[ DISPATCH EXECUTED ]</span>
                <span className="text-[#E5A823]">250_OK</span>
              </div>
              <p className="text-neutral-700 leading-relaxed mb-4">
                {feedbackMessage ||
                  "A single-use SHA-256 authorization token has been dispatched."}
              </p>
              <div className="bg-white border border-[#111111] p-3 text-neutral-900 break-all mb-4 font-bold">
                DESTINATION: {submittedEmail}
              </div>
              <p className="text-neutral-500 text-[11px] leading-relaxed mb-4">
                Check your terminal logs or inbox and click the authentication URL. This token expires in 15 minutes.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSubmittedEmail(null);
                  setEmail("");
                  clearError();
                }}
                className="text-[#111111] underline hover:text-[#E5A823] text-xs uppercase tracking-wider font-bold"
              >
                [ Use Different Email Address ]
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <div className="border border-red-700 bg-red-50 text-red-900 p-4 font-mono text-xs rounded-none">
                  <div className="font-bold uppercase mb-1">[ AUTHENTICATION_ERROR ]</div>
                  <div>{error}</div>
                </div>
              )}

              <div>
                <label
                  htmlFor="email"
                  className="block font-mono text-xs font-bold uppercase tracking-wider text-[#111111] mb-2"
                >
                  Analyst Institutional Email:
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@firm.com"
                  disabled={isLoading}
                  className="w-full bg-[#F7F7F5] border border-[#111111] text-[#111111] font-mono text-sm px-4 py-3 rounded-none outline-none focus:bg-white focus:border-[#E5A823] transition-colors"
                />
              </div>

              <div>
                <button
                  type="submit"
                  disabled={isLoading || !email.trim()}
                  className="w-full bg-[#111111] hover:bg-[#E5A823] text-white hover:text-black font-mono text-xs md:text-sm font-bold uppercase tracking-wider py-4 px-6 border border-[#111111] rounded-none transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {isLoading ? "[ DISPATCHING CRYPTOGRAPHIC TOKEN... ]" : "[ -> Request Access Token ]"}
                </button>
              </div>

              <div className="font-mono text-[11px] text-neutral-500 border-t border-neutral-200 pt-4 leading-relaxed">
                SECURITY: No static passwords stored. Cryptographic single-use magic tokens generated with SHA-256 anti-replay protection.
              </div>
            </form>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#111111] px-6 py-4 flex flex-wrap items-center justify-between font-mono text-xs text-neutral-600 bg-[#F7F7F5]">
        <div>FINANCIAL CRAG GATEWAY &copy; 2026</div>
        <div>STRICT DESIGN STANDARD // ROUNDED-NONE</div>
      </footer>
    </div>
  );
}
