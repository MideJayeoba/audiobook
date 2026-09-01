export default function Header() {
  return (
    <header className="flex flex-col items-center text-center space-y-4 py-8 animate-fade-in relative">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-lg h-32 bg-brand-500/20 blur-[100px] pointer-events-none rounded-full"></div>
      
      <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-brand-300 shadow-[0_0_15px_rgba(16,185,129,0.15)]">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500"></span>
        </span>
        Audiobook Platform
      </span>
      
      <h1 className="text-4xl font-bold tracking-tight md:text-6xl max-w-4xl">
        <span className="bg-gradient-to-br from-white via-slate-200 to-slate-500 bg-clip-text text-transparent drop-shadow-sm">
          Convert documents into
        </span>
        <br />
        <span className="bg-gradient-to-r from-brand-400 to-emerald-600 bg-clip-text text-transparent filter drop-shadow-[0_0_20px_rgba(16,185,129,0.3)]">
          rich, accessible audiobooks.
        </span>
      </h1>
      
      <p className="max-w-2xl text-base text-slate-400 md:text-lg font-light">
        Powered by Django & FastAPI backend with a premium React frontend. Cloud-ready architecture for seamless reading.
      </p>
    </header>
  );
}
