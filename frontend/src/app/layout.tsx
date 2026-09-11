import type { Metadata } from "next";
import { Newsreader, JetBrains_Mono, Geist } from "next/font/google";
import { AuthProvider } from "@/context/AuthContext";
import "./globals.css";

const newsreader = Newsreader({
  variable: "--font-serif",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SEC Intelligence Terminal | Financial CRAG",
  description: "Enterprise Corrective-RAG system for SEC 10-K filings and financial due-diligence.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${newsreader.variable} ${jetbrainsMono.variable} ${geistSans.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-serif bg-[#F7F7F5] text-[#111111]">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
