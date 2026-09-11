"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

function VerifyTokenContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { verifyToken } = useAuth();

  const [statusText, setStatusText] = useState<string>(
    "VALIDATING CRYPTOGRAPHIC TOKEN..."
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);

  useEffect(() => {
    const token = searchParams.get("token");

    if (!token) {
      setErrorMessage("Missing authentication token parameter in URL.");
      return;
    }

    let isMounted = true;

    async function executeVerification() {
      try {
        if (!token) return;
        setStatusText("CHECKING DATABASE HASH & ANTI-REPLAY REGISTER...");
        const user = await verifyToken(token);

        if (isMounted) {
          setIsSuccess(true);
          setStatusText(
            `ACCESS GRANTED FOR [${user.email.toUpperCase()}] -> REDIRECTING...`
          );
          setTimeout(() => {
            router.push("/dashboard");
          }, 1200);
        }
      } catch (err) {
        if (isMounted) {
          const detail =
            err instanceof Error
              ? err.message
              : "Verification failed. Token may be expired or already consumed.";
          setErrorMessage(detail);
        }
      }
    }

    executeVerification();

    return () => {
      isMounted = false;
    };
  }, [searchParams, verifyToken, router]);

  return (
    <div className="max-w-xl w-full border border-[#111111] bg-white p-8 md:p-10 rounded-none">
      <div className="font-sans text-xs tracking-widest uppercase text-neutral-500 mb-3 pb-2 border-b border-[#111111]">
        Analyst Verification Gateway
      </div>

      <h1 className="font-sans text-2xl font-black uppercase tracking-tight text-[#111111] mb-6">
        Session Handshake
      </h1>

      {errorMessage ? (
        <div className="space-y-6">
          <div className="border border-red-700 bg-red-50 text-red-900 p-5 font-mono text-xs rounded-none">
            <div className="font-bold uppercase tracking-wider mb-2">
              [ 400_VERIFICATION_REJECTED ]
            </div>
            <div className="leading-relaxed mb-2">{errorMessage}</div>
            <div className="text-red-700 text-[11px]">
              Note: Single-use tokens are immediately consumed upon activation or expire after 15 minutes.
            </div>
          </div>

          <div>
            <Link
              href="/login"
              className="inline-block w-full text-center bg-[#111111] hover:bg-[#E5A823] text-white hover:text-black font-mono text-xs font-bold uppercase tracking-wider py-4 px-6 border border-[#111111] rounded-none transition-colors"
            >
              [ -&gt; Return to Terminal Login ]
            </Link>
          </div>
        </div>
      ) : (
        <div className="border border-[#111111] bg-[#111111] text-[#F7F7F5] p-6 font-mono text-xs space-y-3">
          <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
            <span className="text-neutral-400">HANDSHAKE STATUS</span>
            <span className={isSuccess ? "text-[#E5A823]" : "text-neutral-300"}>
              {isSuccess ? "[ SUCCESS ]" : "[ PROCESSING ]"}
            </span>
          </div>
          <div className="text-sm font-bold text-white pt-2">
            {statusText}
          </div>
          <div className="text-neutral-500 text-[11px] pt-4 border-t border-neutral-800">
            HTTP-only cookie transit will be activated upon session establishment.
          </div>
        </div>
      )}
    </div>
  );
}

export default function VerifyPage() {
  return (
    <div className="flex-1 flex flex-col min-h-screen bg-[#F7F7F5] text-[#111111]">
      <header className="border-b border-[#111111] px-6 py-3 flex items-center justify-between font-mono text-xs tracking-wider uppercase bg-[#F7F7F5]">
        <Link href="/" className="bg-[#111111] text-[#F7F7F5] px-2 py-0.5 font-bold hover:bg-[#E5A823] hover:text-black transition-colors">
          CRAG-SEC
        </Link>
        <span className="text-neutral-600">HANDSHAKE_NODE</span>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <Suspense
          fallback={
            <div className="max-w-xl w-full border border-[#111111] bg-white p-8 font-mono text-xs">
              [ INITIALIZING VERIFICATION HANDSHAKE... ]
            </div>
          }
        >
          <VerifyTokenContent />
        </Suspense>
      </main>

      <footer className="border-t border-[#111111] px-6 py-4 font-mono text-xs text-neutral-600 bg-[#F7F7F5]">
        SEC DUE-DILIGENCE CRAG TERMINAL // VERIFICATION
      </footer>
    </div>
  );
}
