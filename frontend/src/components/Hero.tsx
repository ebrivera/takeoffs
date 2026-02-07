export function Hero() {
  return (
    <section
      id="hero"
      className="blueprint-grid-dark relative flex min-h-[100vh] items-center overflow-hidden pt-16"
    >
      {/* Radial glow */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/3 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blueprint-500/8 blur-[120px]" />
        <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-navy-950 to-transparent" />
      </div>

      <div className="relative z-10 mx-auto max-w-6xl px-6 py-24 md:py-32">
        <div className="grid items-center gap-16 lg:grid-cols-2">
          {/* Left - Copy */}
          <div className="max-w-xl">
            {/* Tag */}
            <div className="animate-fade-up mb-6 inline-flex items-center gap-2 rounded-full border border-blueprint-400/20 bg-blueprint-500/5 px-4 py-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span className="font-mono text-xs tracking-wider text-blueprint-300">
                NOW IN EARLY ACCESS
              </span>
            </div>

            <h1 className="animate-fade-up delay-100 text-4xl font-extrabold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-6xl">
              Cost estimates{" "}
              <span className="bg-gradient-to-r from-blueprint-300 to-blueprint-400 bg-clip-text text-transparent">
                in minutes,
              </span>{" "}
              not days.
            </h1>

            <p className="animate-fade-up delay-200 mt-6 max-w-md text-lg leading-relaxed text-navy-300">
              Takeoffs reads your construction plans and automatically generates
              accurate material quantities and cost breakdowns. Built for
              estimators who are tired of manual takeoffs.
            </p>

            {/* CTA Group */}
            <div
              id="cta"
              className="animate-fade-up delay-300 mt-10 flex flex-col gap-4 sm:flex-row sm:items-center"
            >
              <a
                href="#contact"
                className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-sm bg-accent-500 px-7 py-3.5 text-sm font-bold tracking-wide text-white transition-all hover:bg-accent-400 hover:shadow-lg hover:shadow-accent-500/20"
              >
                <span>Request a Demo</span>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  className="transition-transform group-hover:translate-x-0.5"
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
                href="#how-it-works"
                className="inline-flex items-center justify-center gap-2 px-6 py-3.5 text-sm font-medium text-navy-300 transition-colors hover:text-white"
              >
                See How It Works
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 12 12"
                  fill="none"
                  className="transition-transform group-hover:translate-y-0.5"
                >
                  <path
                    d="M6 1v10m0 0l4-4m-4 4L2 7"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </a>
            </div>

            {/* Social proof */}
            <div className="animate-fade-up delay-400 mt-12 flex items-center gap-6 border-t border-white/5 pt-8">
              <div>
                <div className="font-mono text-2xl font-bold text-white">
                  90%
                </div>
                <div className="text-xs tracking-wide text-navy-400">
                  Faster estimates
                </div>
              </div>
              <div className="h-8 w-px bg-white/10" />
              <div>
                <div className="font-mono text-2xl font-bold text-white">
                  &plusmn;3%
                </div>
                <div className="text-xs tracking-wide text-navy-400">
                  Accuracy range
                </div>
              </div>
              <div className="h-8 w-px bg-white/10" />
              <div>
                <div className="font-mono text-2xl font-bold text-white">
                  24hr
                </div>
                <div className="text-xs tracking-wide text-navy-400">
                  Turnaround
                </div>
              </div>
            </div>
          </div>

          {/* Right - Visual */}
          <div className="animate-fade-up delay-400 hidden lg:block">
            <div className="relative">
              {/* Mockup card */}
              <div className="rounded-lg border border-white/10 bg-navy-900/60 p-6 shadow-2xl shadow-black/40 backdrop-blur-sm">
                {/* Top bar */}
                <div className="mb-5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                    <span className="font-mono text-xs text-navy-400">
                      Estimate #2847
                    </span>
                  </div>
                  <span className="rounded border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] font-medium text-emerald-400">
                    COMPLETE
                  </span>
                </div>

                {/* Table header */}
                <div className="mb-2 grid grid-cols-4 gap-3 border-b border-white/5 pb-2">
                  <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-navy-500">
                    Item
                  </span>
                  <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-navy-500">
                    Qty
                  </span>
                  <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-navy-500">
                    Unit
                  </span>
                  <span className="text-right font-mono text-[10px] font-medium uppercase tracking-wider text-navy-500">
                    Cost
                  </span>
                </div>

                {/* Table rows */}
                {[
                  { item: "Concrete Footing", qty: "48", unit: "CY", cost: "$14,400" },
                  { item: "Rebar #5", qty: "2,800", unit: "LF", cost: "$4,200" },
                  { item: "Form Work", qty: "1,920", unit: "SF", cost: "$11,520" },
                  { item: "Anchor Bolts", qty: "96", unit: "EA", cost: "$1,920" },
                  { item: "Waterproofing", qty: "3,400", unit: "SF", cost: "$10,200" },
                ].map((row, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-4 gap-3 border-b border-white/[0.03] py-2.5"
                  >
                    <span className="text-sm text-navy-200">{row.item}</span>
                    <span className="font-mono text-sm text-navy-300">
                      {row.qty}
                    </span>
                    <span className="font-mono text-sm text-navy-400">
                      {row.unit}
                    </span>
                    <span className="text-right font-mono text-sm text-white">
                      {row.cost}
                    </span>
                  </div>
                ))}

                {/* Total */}
                <div className="mt-4 flex items-center justify-between border-t border-blueprint-400/20 pt-4">
                  <span className="text-sm font-semibold text-navy-300">
                    Total Estimate
                  </span>
                  <span className="font-mono text-lg font-bold text-white">
                    $42,240
                  </span>
                </div>
              </div>

              {/* Floating accent */}
              <div className="absolute -right-4 -top-4 rounded border border-blueprint-400/30 bg-navy-900/80 px-3 py-2 shadow-lg backdrop-blur-sm">
                <div className="font-mono text-[10px] text-navy-400">
                  Processing Time
                </div>
                <div className="font-mono text-lg font-bold text-blueprint-300">
                  2m 14s
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
