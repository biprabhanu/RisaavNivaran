// Placeholder shown for the split second while a lazily-loaded page's code downloads.
export default function PageLoader() {
  return (
    <div className="flex items-center justify-center py-24 text-slate-500" role="status" aria-live="polite">
      <span className="inline-block w-5 h-5 mr-3 rounded-full border-2 border-teal-500 border-t-transparent animate-spin" />
      <span className="text-sm font-medium">Loading…</span>
    </div>
  );
}
