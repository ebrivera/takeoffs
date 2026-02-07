export function Footer() {
  return (
    <footer id="contact" className="relative border-t border-white/5 bg-navy-950">
      {/* CTA Band */}
      <div className="border-b border-white/5">
        <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">
          <div className="grid items-center gap-10 lg:grid-cols-2">
            <div>
              <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Ready to stop counting manually?
              </h2>
              <p className="mt-4 max-w-md text-lg text-navy-400">
                Join estimators at leading firms who are already using Takeoffs
                to win more bids, faster.
              </p>
            </div>
            <div className="flex flex-col gap-4 sm:flex-row lg:justify-end">
              <a
                href="mailto:hello@takeoffs.dev"
                className="inline-flex items-center justify-center gap-2 rounded-sm bg-accent-500 px-7 py-3.5 text-sm font-bold tracking-wide text-white transition-all hover:bg-accent-400 hover:shadow-lg hover:shadow-accent-500/20"
              >
                Request Early Access
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                >
                  <path
                    d="M1 7h12m0 0L8 2m5 5L8 12"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </a>
              <a
                href="mailto:hello@takeoffs.dev"
                className="inline-flex items-center justify-center rounded-sm border border-white/10 px-7 py-3.5 text-sm font-medium text-navy-300 transition-all hover:border-white/20 hover:text-white"
              >
                Contact Sales
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Footer links */}
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand */}
          <div className="lg:col-span-1">
            <a href="#" className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-sm border border-blueprint-400/40 bg-blueprint-500/10">
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 16 16"
                  fill="none"
                  className="text-blueprint-300"
                >
                  <path d="M2 3h12v2H9v8H7V5H2V3z" fill="currentColor" />
                </svg>
              </div>
              <span className="text-sm font-bold tracking-wide text-white">
                TAKEOFFS
              </span>
            </a>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-navy-500">
              Automated cost estimation for construction professionals.
              Accurate. Fast. Reliable.
            </p>
          </div>

          {/* Product */}
          <div>
            <h4 className="mb-4 font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-navy-500">
              Product
            </h4>
            <ul className="space-y-2.5">
              {["How It Works", "Pricing", "Integrations", "API Docs"].map(
                (item) => (
                  <li key={item}>
                    <a
                      href="#"
                      className="text-sm text-navy-400 transition-colors hover:text-white"
                    >
                      {item}
                    </a>
                  </li>
                )
              )}
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="mb-4 font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-navy-500">
              Company
            </h4>
            <ul className="space-y-2.5">
              {["About", "Team", "Careers", "Blog"].map((item) => (
                <li key={item}>
                  <a
                    href="#"
                    className="text-sm text-navy-400 transition-colors hover:text-white"
                  >
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="mb-4 font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-navy-500">
              Legal
            </h4>
            <ul className="space-y-2.5">
              {["Privacy Policy", "Terms of Service", "Security"].map(
                (item) => (
                  <li key={item}>
                    <a
                      href="#"
                      className="text-sm text-navy-400 transition-colors hover:text-white"
                    >
                      {item}
                    </a>
                  </li>
                )
              )}
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-white/5 pt-8 sm:flex-row">
          <p className="font-mono text-xs text-navy-600">
            &copy; {new Date().getFullYear()} Takeoffs, Inc. All rights
            reserved.
          </p>
          <div className="flex items-center gap-4">
            {/* LinkedIn */}
            <a
              href="#"
              className="text-navy-600 transition-colors hover:text-navy-400"
              aria-label="LinkedIn"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
              </svg>
            </a>
            {/* Twitter / X */}
            <a
              href="#"
              className="text-navy-600 transition-colors hover:text-navy-400"
              aria-label="X (Twitter)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
              </svg>
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
