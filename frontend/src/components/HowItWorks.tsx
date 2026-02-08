const steps = [
  {
    number: "01",
    title: "Upload Plans",
    description:
      "Drop your blueprints, PDFs, or CAD files into Cantena. We support all standard construction document formats.",
    icon: (
      <svg
        width="28"
        height="28"
        viewBox="0 0 28 28"
        fill="none"
        className="text-blueprint-400"
      >
        <path
          d="M14 4v14m0-14L9 9m5-5l5 5"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M4 18v2a4 4 0 004 4h12a4 4 0 004-4v-2"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    number: "02",
    title: "Automatic Extraction",
    description:
      "Our engine reads every dimension, symbol, and annotation. Material quantities, linear footage, and areas are extracted automatically.",
    icon: (
      <svg
        width="28"
        height="28"
        viewBox="0 0 28 28"
        fill="none"
        className="text-blueprint-400"
      >
        <rect
          x="3"
          y="3"
          width="22"
          height="22"
          rx="3"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <path
          d="M8 14h12M14 8v12"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx="8" cy="8" r="1.5" fill="currentColor" opacity="0.4" />
        <circle cx="20" cy="8" r="1.5" fill="currentColor" opacity="0.4" />
        <circle cx="8" cy="20" r="1.5" fill="currentColor" opacity="0.4" />
        <circle cx="20" cy="20" r="1.5" fill="currentColor" opacity="0.4" />
      </svg>
    ),
  },
  {
    number: "03",
    title: "Review & Export",
    description:
      "Get a detailed cost breakdown with line-item accuracy. Review, adjust, and export to Excel or your estimating system.",
    icon: (
      <svg
        width="28"
        height="28"
        viewBox="0 0 28 28"
        fill="none"
        className="text-blueprint-400"
      >
        <path
          d="M9 14l3 3 7-7"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <rect
          x="3"
          y="3"
          width="22"
          height="22"
          rx="3"
          stroke="currentColor"
          strokeWidth="1.5"
        />
      </svg>
    ),
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="blueprint-grid relative py-24 md:py-32">
      {/* Gradient transitions */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-navy-950 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-navy-950 to-transparent" />

      <div className="mx-auto max-w-6xl px-6">
        {/* Section header */}
        <div className="mb-16 max-w-xl">
          <h2 className="text-3xl font-bold tracking-tight text-navy-950 sm:text-4xl">
            From blueprint to bid{" "}
            <span className="text-blueprint-500">in three steps.</span>
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-navy-800">
            No more counting, measuring, or manual data entry. Cantena handles
            the tedious work so you can focus on winning contracts.
          </p>
        </div>

        {/* Steps */}
        <div className="grid gap-8 md:grid-cols-3">
          {steps.map((step, i) => (
            <div
              key={step.number}
              className="group relative rounded-lg border border-navy-200/60 bg-white/70 p-8 shadow-sm backdrop-blur-sm transition-all hover:border-blueprint-300/50 hover:shadow-md hover:shadow-blueprint-500/5"
            >
              {/* Connection line (desktop) */}
              {i < steps.length - 1 && (
                <div className="absolute -right-4 top-12 hidden h-px w-8 bg-navy-200 md:block" />
              )}

              {/* Step number */}
              <div className="mb-6 flex items-start justify-between">
                <div className="flex h-12 w-12 items-center justify-center rounded-sm border border-blueprint-200/60 bg-blueprint-50/80 transition-colors group-hover:border-blueprint-300/60 group-hover:bg-blueprint-100/60">
                  {step.icon}
                </div>
                <span className="font-mono text-4xl font-bold text-navy-100 transition-colors group-hover:text-blueprint-100">
                  {step.number}
                </span>
              </div>

              <h3 className="mb-3 text-xl font-bold text-navy-900">
                {step.title}
              </h3>
              <p className="text-sm leading-relaxed text-navy-500">
                {step.description}
              </p>
            </div>
          ))}
        </div>

        {/* Capabilities row */}
        <div className="mt-16 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { label: "PDF & CAD Support", detail: "All standard formats" },
            { label: "CSI MasterFormat", detail: "Organized by trade" },
            { label: "Excel Export", detail: "One-click download" },
            { label: "Audit Trail", detail: "Every calculation tracked" },
          ].map((cap) => (
            <div
              key={cap.label}
              className="rounded border border-navy-200/40 bg-white/50 px-5 py-4 backdrop-blur-sm"
            >
              <div className="text-sm font-semibold text-navy-800">
                {cap.label}
              </div>
              <div className="mt-0.5 font-mono text-xs text-navy-400">
                {cap.detail}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
