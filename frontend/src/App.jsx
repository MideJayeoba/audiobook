import Header from "./components/Header";

const cards = [
  {
    title: "Upload PDF",
    description: "Drag and drop a PDF file, validate type and size, and queue conversion."
  },
  {
    title: "Track Progress",
    description: "Monitor extraction and TTS jobs with real-time status updates."
  },
  {
    title: "Play & Download",
    description: "Stream generated audio and manage your conversion history."
  }
];

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-10 md:px-8">
        <Header />
        <section className="grid gap-4 md:grid-cols-3">
          {cards.map((card) => (
            <article key={card.title} className="rounded-xl border border-slate-800 bg-slate-900/80 p-5">
              <h2 className="text-lg font-semibold text-white">{card.title}</h2>
              <p className="mt-2 text-sm text-slate-300">{card.description}</p>
            </article>
          ))}
        </section>
        <section className="rounded-xl border border-brand-700/40 bg-brand-500/10 p-6">
          <h3 className="text-xl font-semibold text-brand-100">API-First Platform Starter</h3>
          <p className="mt-2 text-sm text-brand-50/90">
            This UI is a skeleton. Connect it to the Django API endpoints under <code>/api/documents/</code>
            and to async status notifications as you implement the roadmap.
          </p>
        </section>
      </div>
    </div>
  );
}
