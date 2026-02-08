function Feature() {
  return (
    <div className="blueprint-grid-dark w-full py-20 lg:py-40">
      <div className="container mx-auto">
        <div className="flex flex-col gap-10">
          <div className="flex gap-4 flex-col items-start">
            <div className="flex gap-2 flex-col">
              <h2 className="text-3xl md:text-5xl tracking-tighter max-w-xl font-regular text-left">
                Made for your workflow.
              </h2>
              <p className="text-lg max-w-xl lg:max-w-lg leading-relaxed tracking-tight text-navy-800 text-left">
                Help your takeoffs take off.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
            <div className="rounded-2xl border border-white/65 bg-white/68 h-full lg:col-span-2 p-6 shadow-[0_16px_48px_rgba(17,17,17,0.08)] backdrop-blur-sm aspect-square lg:aspect-auto flex items-center justify-center text-center">
              <div className="flex max-w-xl flex-col items-center">
                <h3 className="text-2xl font-semibold tracking-tight text-navy-900">
                  Tune Every Estimate Parameter
                </h3>
                <p className="mt-3 text-navy-700 max-w-2xl text-base leading-relaxed">
                  Adjust assumptions before finalizing takeoffs. Swap structural
                  material types, modify spec-level inputs, and instantly see
                  updated quantity and cost projections.
                </p>
              </div>
            </div>
            <div className="rounded-2xl border border-white/65 bg-white/68 aspect-square p-6 shadow-[0_16px_48px_rgba(17,17,17,0.08)] backdrop-blur-sm flex items-center justify-center text-center">
              <div className="flex max-w-xs flex-col items-center">
                <h3 className="text-2xl font-semibold tracking-tight text-navy-900">
                  Drag, Drop, Done.
                </h3>
                <p className="mt-3 text-navy-700 text-base leading-relaxed">
                  Upload floor plans and receive clear takeoff and pricing
                  outputs in minutes.
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-white/65 bg-white/68 aspect-square p-6 shadow-[0_16px_48px_rgba(17,17,17,0.08)] backdrop-blur-sm flex items-center justify-center text-center">
              <div className="flex max-w-xs flex-col items-center">
                <h3 className="text-xl font-semibold tracking-tight text-navy-900">
                  Built for GCs & Trades
                </h3>
                <p className="mt-3 text-navy-700 text-base leading-relaxed">
                  General contractors can review full-scope pricing, while
                  subcontractors can filter to only the materials and costs for
                  their trade.
                </p>
              </div>
            </div>
            <div className="rounded-2xl border border-white/65 bg-white/68 h-full lg:col-span-2 p-6 shadow-[0_16px_48px_rgba(17,17,17,0.08)] backdrop-blur-sm aspect-square lg:aspect-auto flex items-center justify-center text-center">
              <div className="flex max-w-xl flex-col items-center">
                <h3 className="text-2xl font-semibold tracking-tight text-navy-900">
                  Bid-Ready Reports, Fully Traceable
                </h3>
                <p className="mt-3 text-navy-700 max-w-2xl text-base leading-relaxed">
                  Generate clean summaries for submission while keeping a clear
                  audit trail of every quantity, assumption, and cost change.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export { Feature };
