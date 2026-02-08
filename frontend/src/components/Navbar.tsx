"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="fixed top-0 z-50 w-full border-b border-white/5 bg-navy-950/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center">
          <Image
            src="/branding/cantena-logo-white-cropped.png"
            alt="Cantena"
            width={490}
            height={170}
            priority
            className="h-10 w-auto"
          />
        </Link>

        {/* Desktop links */}
        <div className="hidden items-center gap-8 md:flex">
          <a
            href="#cta"
            className="rounded-sm border border-blueprint-400/40 bg-blueprint-500/10 px-5 py-2 text-sm font-semibold tracking-wide text-blueprint-300 transition-all hover:border-blueprint-400/80 hover:bg-blueprint-500/20 hover:text-white"
          >
            Request a Demo
          </a>
        </div>

        {/* Mobile menu button */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="flex h-10 w-10 items-center justify-center rounded md:hidden"
          aria-label="Toggle menu"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            className="text-navy-300"
          >
            {mobileOpen ? (
              <path
                d="M5 5l10 10M15 5L5 15"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            ) : (
              <path
                d="M3 5h14M3 10h14M3 15h14"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="border-t border-white/5 bg-navy-950/95 backdrop-blur-xl md:hidden">
          <div className="flex flex-col gap-1 px-6 py-4">
            <a
              href="#cta"
              onClick={() => setMobileOpen(false)}
              className="rounded-sm border border-blueprint-400/40 bg-blueprint-500/10 px-5 py-2.5 text-center text-sm font-semibold text-blueprint-300 transition-all hover:border-blueprint-400/80 hover:text-white"
            >
              Request a Demo
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}
