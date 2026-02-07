"use client";

import { useState } from "react";

const navLinks = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Team", href: "#team" },
  { label: "Contact", href: "#contact" },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="fixed top-0 z-50 w-full border-b border-white/5 bg-navy-950/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        {/* Logo */}
        <a href="#" className="flex items-center gap-2.5">
          {/* Geometric T mark */}
          <div className="flex h-8 w-8 items-center justify-center rounded-sm border border-blueprint-400/60 bg-blueprint-500/10">
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              className="text-blueprint-300"
            >
              <path
                d="M2 3h12v2H9v8H7V5H2V3z"
                fill="currentColor"
              />
            </svg>
          </div>
          <span className="text-lg font-bold tracking-wide text-white">
            TAKEOFFS
          </span>
        </a>

        {/* Desktop links */}
        <div className="hidden items-center gap-8 md:flex">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium tracking-wide text-navy-300 transition-colors hover:text-white"
            >
              {link.label}
            </a>
          ))}
          <a
            href="#cta"
            className="rounded-sm border border-blueprint-400/40 bg-blueprint-500/10 px-5 py-2 text-sm font-semibold tracking-wide text-blueprint-300 transition-all hover:border-blueprint-400/80 hover:bg-blueprint-500/20 hover:text-white"
          >
            Get Early Access
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
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="rounded px-3 py-2.5 text-sm font-medium text-navy-300 transition-colors hover:bg-white/5 hover:text-white"
              >
                {link.label}
              </a>
            ))}
            <a
              href="#cta"
              onClick={() => setMobileOpen(false)}
              className="mt-2 rounded-sm border border-blueprint-400/40 bg-blueprint-500/10 px-5 py-2.5 text-center text-sm font-semibold text-blueprint-300 transition-all hover:border-blueprint-400/80 hover:text-white"
            >
              Get Early Access
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}
