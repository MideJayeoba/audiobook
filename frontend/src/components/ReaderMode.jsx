export default function ReaderMode({ 
  selectedVoice, setSelectedVoice, voiceOptions,
  readerDocumentId, setReaderDocumentId, seekableDocuments,
  readerSections, activeReaderSection, selectReaderSection,
  readSection, isLoadingAudio, readerDocument 
}) {
  return (
    <section className="glass rounded-2xl p-6 lg:p-8 animate-slide-up relative overflow-hidden group" style={{ animationDelay: '200ms' }}>
       <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[500px] w-[500px] rounded-full bg-emerald-500/5 blur-[100px] pointer-events-none"></div>

       <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/50 pb-6">
          <h2 className="text-2xl font-semibold tracking-tight text-white">Reader Mode</h2>
          <div className="flex items-center gap-3 bg-slate-900/50 p-1.5 rounded-xl border border-slate-800">
             <span className="text-xs uppercase tracking-wider text-slate-400 font-medium pl-3">Voice</span>
             <select
               value={selectedVoice}
               onChange={(event) => setSelectedVoice(event.target.value)}
               className="rounded-lg bg-slate-800/80 px-3 py-1.5 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-brand-500/50 border border-slate-700/50 cursor-pointer"
             >
               {voiceOptions.map((voice) => (
                 <option key={voice.value} value={voice.value}>
                   {voice.label || voice.value}
                 </option>
               ))}
             </select>
          </div>
       </div>

       <div className="mt-6 grid gap-6 lg:grid-cols-[280px_1fr]">
          <div className="flex flex-col gap-6">
             <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-slate-500 font-medium">Document</label>
                <select
                  value={readerDocumentId}
                  onChange={(event) => setReaderDocumentId(event.target.value)}
                  className="w-full rounded-xl bg-slate-900/50 px-4 py-3 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-brand-500/50 border border-slate-700/50 cursor-pointer transition-all hover:border-slate-600"
                >
                  <option value="">Select a document</option>
                  {seekableDocuments.map((document) => (
                    <option key={document.id} value={document.id}>
                      {document.title}
                    </option>
                  ))}
                </select>
             </div>

             <div className="space-y-2 flex-1 flex flex-col min-h-[300px]">
                <label className="text-xs uppercase tracking-wider text-slate-500 font-medium flex items-center justify-between">
                  Sections
                  <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded-full">{readerSections.length}</span>
                </label>
                <div className="flex-1 overflow-y-auto pr-2 space-y-1.5 max-h-[400px]">
                  {readerSections.map((section, index) => {
                    const isActive = Number(activeReaderSection?.index) === Number(section.index);
                    return (
                      <button
                        key={`reader-${section.index}`}
                        type="button"
                        onClick={() => readerDocument && selectReaderSection(readerDocument.id, section.index)}
                        className={`w-full rounded-xl px-4 py-3 text-left text-sm transition-all duration-300 ${
                          isActive 
                            ? "bg-brand-500/20 text-brand-50 border border-brand-500/50 shadow-[0_0_15px_rgba(16,185,129,0.1)]" 
                            : "bg-slate-900/30 text-slate-300 hover:bg-slate-800/80 hover:text-slate-100 border border-transparent"
                        }`}
                      >
                        <span className="line-clamp-2">{section.title || `Section ${index + 1}`}</span>
                      </button>
                    );
                  })}
                  {!readerSections.length && (
                    <div className="flex flex-col items-center justify-center py-10 text-slate-500 border-2 border-dashed border-slate-800/50 rounded-xl">
                       <svg className="w-6 h-6 mb-2 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                       <p className="text-xs">No sections available</p>
                    </div>
                  )}
                </div>
             </div>
          </div>

          <div className="flex flex-col rounded-2xl border border-slate-700/50 bg-slate-900/40 overflow-hidden shadow-inner relative">
             {activeReaderSection ? (
               <div className="flex flex-col h-full animate-fade-in">
                 <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/50 p-5 bg-slate-900/60">
                   <h3 className="text-xl font-semibold text-slate-100 leading-tight">
                     {activeReaderSection.title || `Section ${Number(activeReaderSection.index) + 1}`}
                   </h3>
                   <button
                     type="button"
                     onClick={() => readSection(readerDocumentId, activeReaderSection.index)}
                     disabled={isLoadingAudio}
                     className="flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-all hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50 hover:shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:-translate-y-0.5 active:translate-y-0"
                   >
                     {isLoadingAudio ? (
                       <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                     ) : (
                       <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                     )}
                     {isLoadingAudio ? "Preparing..." : "Read Aloud"}
                   </button>
                 </div>
                 
                 <div className="p-5 flex-1 overflow-y-auto max-h-[600px]">
                   {readerDocument?.ai_summary && (
                     <div className="mb-6 rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-5 backdrop-blur-sm">
                       <div className="flex items-center justify-between gap-2 mb-3">
                         <h4 className="text-xs uppercase tracking-wider text-indigo-300 font-semibold flex items-center gap-2">
                           <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                           AI Summary
                         </h4>
                         <span className="rounded-full bg-indigo-500/20 px-2.5 py-1 text-[10px] font-semibold text-indigo-200 border border-indigo-500/30">
                           {readerDocument.ai_provider === "groq" ? (readerDocument.ai_anchored ? "Groq (Anchored)" : "Groq") : "Local"}
                         </span>
                       </div>
                       <p className="text-sm text-indigo-100/90 leading-relaxed">{readerDocument.ai_summary}</p>
                     </div>
                   )}
                   
                   <div className="prose prose-invert max-w-none">
                     <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-slate-300 font-serif">
                       {activeReaderSection.text}
                     </p>
                   </div>
                 </div>
               </div>
             ) : (
               <div className="flex flex-col items-center justify-center h-full text-slate-500 p-12 text-center">
                 <svg className="w-16 h-16 mb-4 opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                 <p className="text-xl font-medium text-slate-400 mb-2">Ready to read</p>
                 <p className="text-sm">Select a document and section from the sidebar to begin reading.</p>
               </div>
             )}
          </div>
       </div>
    </section>
  );
}
