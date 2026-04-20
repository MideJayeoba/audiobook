export default function Header() {
  return (
    <header className="space-y-3">
      <p className="inline-flex rounded-full border border-brand-500/60 bg-brand-500/20 px-3 py-1 text-xs uppercase tracking-[0.2em] text-brand-100">
        Audiobook Platform
      </p>
      <h1 className="text-3xl font-bold leading-tight md:text-5xl">
        Convert documents into rich, accessible audiobooks.
      </h1>
      <p className="max-w-2xl text-sm text-slate-300 md:text-base">
        Django + FastAPI backend, React + Tailwind frontend, cloud-ready architecture.
      </p>
    </header>
  );
}
