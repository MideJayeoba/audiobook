export default function DocumentUploader({ title, setTitle, file, setFile, isUploading, message, handleUpload }) {
  return (
    <section className="glass flex-1 rounded-2xl p-6 lg:p-8 animate-slide-up relative overflow-hidden group">
      <div className="absolute -right-20 -top-20 h-40 w-40 rounded-full bg-brand-500/10 blur-3xl transition-transform duration-700 group-hover:scale-150"></div>
      
      <div className="relative z-10">
        <h2 className="text-2xl font-semibold tracking-tight text-white">Upload PDF</h2>
        <p className="mt-1 text-sm text-slate-400">Select a document to convert into an audiobook.</p>
        
        <form onSubmit={handleUpload} className="mt-6 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs uppercase tracking-wider text-slate-500 font-medium">Document Title</label>
            <input
              type="text"
              placeholder="e.g., The Great Gatsby"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="w-full rounded-xl border border-slate-700/50 bg-slate-900/50 px-4 py-3 text-sm text-slate-100 outline-none transition-all focus:border-brand-500 focus:bg-slate-900 focus:ring-2 focus:ring-brand-500/20"
            />
          </div>
          
          <div className="flex flex-col gap-1.5">
            <label className="text-xs uppercase tracking-wider text-slate-500 font-medium">File Selection</label>
            <div className="relative group/file cursor-pointer">
              <input
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => {
                  const selected = event.target.files?.[0] || null;
                  setFile(selected);
                  if (selected && !title.trim()) {
                    setTitle(selected.name.replace(/\.pdf$/i, ""));
                  }
                }}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
              />
              <div className="flex items-center justify-center w-full rounded-xl border-2 border-dashed border-slate-700/50 bg-slate-900/20 px-4 py-8 transition-all group-hover/file:border-brand-500/50 group-hover/file:bg-brand-500/5 text-center">
                <div className="flex flex-col items-center gap-2">
                  <svg className="w-8 h-8 text-slate-500 group-hover/file:text-brand-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <span className="text-sm font-medium text-slate-300">
                    {file ? file.name : "Click or drag PDF to upload"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={isUploading}
            className="mt-2 w-full rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-500/20 transition-all hover:bg-brand-500 hover:shadow-brand-500/40 disabled:opacity-50 disabled:cursor-not-allowed hover:-translate-y-0.5 active:translate-y-0"
          >
            {isUploading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing...
              </span>
            ) : "Upload and Process"}
          </button>
        </form>
        
        {message && message !== "Ready." && (
          <div className="mt-4 rounded-lg bg-slate-800/50 p-3 border border-slate-700/50 animate-fade-in text-sm text-slate-300">
            {message}
          </div>
        )}
      </div>
    </section>
  );
}
