"use client";

import React, { useState } from "react";

interface QueryBarProps {
  onSubmit: (question: string, ticker?: string, year?: number) => void;
  disabled?: boolean;
}

/**
 * Brutalist QueryBar component for financial due-diligence inquiries.
 * Adheres strictly to Design.md:
 * - Zero icons (no Lucide, SVG, or iconography)
 * - Serif font for editorial inquiry textarea (Newsreader)
 * - Monospace font for ticker & year inputs (JetBrains Mono)
 * - Flat, sharp-cornered button with [ EXECUTE QUERY ] in Geist sans-serif
 * - Stark black 1px borders, zero border-radius
 */
export function QueryBar({ onSubmit, disabled = false }: QueryBarProps) {
  const [question, setQuestion] = useState("");
  const [ticker, setTicker] = useState("");
  const [year, setYear] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || disabled) return;

    const parsedYear = year.trim() ? parseInt(year.trim(), 10) : undefined;
    const cleanTicker = ticker.trim() ? ticker.trim().toUpperCase() : undefined;

    onSubmit(
      trimmedQuestion,
      cleanTicker,
      isNaN(parsedYear as number) ? undefined : parsedYear
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full bg-[#F7F7F5] border-t border-[#111111] p-4 flex flex-col md:flex-row gap-3 items-stretch md:items-end rounded-none"
    >
      <div className="flex-1 flex flex-col gap-1">
        <label className="font-mono text-[10px] uppercase tracking-wider text-[#111111] font-semibold">
          ANALYST INQUIRY // DIRECTIVE
        </label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Formulate financial inquiry (e.g., What was Apple's total net sales in FY 2023?)..."
          disabled={disabled}
          rows={2}
          className="w-full font-serif text-sm bg-white text-[#111111] border border-[#111111] p-2.5 rounded-none resize-none focus:outline-none focus:border-[#111111] focus:ring-0 placeholder:text-neutral-400 disabled:opacity-50"
        />
      </div>

      <div className="flex gap-3 items-end">
        <div className="w-24 flex flex-col gap-1">
          <label className="font-mono text-[10px] uppercase tracking-wider text-[#111111] font-semibold">
            TICKER
          </label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL"
            maxLength={10}
            disabled={disabled}
            className="w-full font-mono text-xs uppercase bg-white text-[#111111] border border-[#111111] p-2.5 rounded-none focus:outline-none focus:border-[#111111] focus:ring-0 placeholder:text-neutral-400 disabled:opacity-50"
          />
        </div>

        <div className="w-24 flex flex-col gap-1">
          <label className="font-mono text-[10px] uppercase tracking-wider text-[#111111] font-semibold">
            FY YEAR
          </label>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder="2023"
            min={1990}
            max={2050}
            disabled={disabled}
            className="w-full font-mono text-xs bg-white text-[#111111] border border-[#111111] p-2.5 rounded-none focus:outline-none focus:border-[#111111] focus:ring-0 placeholder:text-neutral-400 disabled:opacity-50"
          />
        </div>

        <button
          type="submit"
          disabled={disabled || !question.trim()}
          className="h-[42px] px-6 font-sans text-xs font-bold uppercase tracking-wider bg-[#111111] text-[#F7F7F5] border border-[#111111] rounded-none hover:bg-white hover:text-[#111111] transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer whitespace-nowrap"
        >
          [ EXECUTE QUERY ]
        </button>
      </div>
    </form>
  );
}
