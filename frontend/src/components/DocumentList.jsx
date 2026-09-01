export default function DocumentList({ statusFilter, setStatusFilter, filteredDocuments, deleteDocument, statusStyles }) {
  const filters = [
    { value: "all", label: "All" },
    { value: "uploaded", label: "Uploaded" },
    { value: "extracting", label: "Extracting" },
    { value: "extracted", label: "Extracted" },
    { value: "completed", label: "Completed" },
    { value: "failed", label: "Failed" }
  ];

  return (
    <section className="glass flex-1 rounded-2xl p-6 lg:p-8 animate-slide-up relative overflow-hidden group" style={{ animationDelay: '100ms' }}>
      <div className="absolute -left-20 -bottom-20 h-40 w-40 rounded-full bg-blue-500/10 blur-3xl transition-transform duration-700 group-hover:scale-150"></div>
      
      <div className="relative z-10 flex flex-col h-full">
        <h2 className="text-2xl font-semibold tracking-tight text-white">Track Progress</h2>
        
        <div className="mt-4 flex flex-wrap gap-2">
          {filters.map((filter) => (
            <button
              key={filter.value}
              type="button"
              onClick={() => setStatusFilter(filter.value)}
              className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                statusFilter === filter.value
                  ? "bg-brand-500 text-white shadow-md shadow-brand-500/20"
                  : "bg-slate-800/50 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700/50"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
        
        <div className="mt-6 flex-1 overflow-x-auto overflow-y-auto max-h-[300px] pr-2">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="px-3 py-3 font-medium uppercase tracking-wider text-xs">Title</th>
                <th className="px-3 py-3 font-medium uppercase tracking-wider text-xs">Status</th>
                <th className="px-3 py-3 font-medium uppercase tracking-wider text-xs text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {filteredDocuments.map((document) => (
                <tr key={document.id} className="group/row hover:bg-slate-800/30 transition-colors">
                  <td className="px-3 py-4 text-slate-200 font-medium truncate max-w-[150px]">{document.title}</td>
                  <td className="px-3 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold shadow-sm ${statusStyles[document.status] || "bg-slate-800 text-slate-300"}`}>
                      {document.status}
                    </span>
                  </td>
                  <td className="px-3 py-4 text-right">
                    <button
                      type="button"
                      onClick={() => deleteDocument(document.id)}
                      className="opacity-0 group-hover/row:opacity-100 rounded-lg bg-rose-500/10 p-2 text-rose-400 transition-all hover:bg-rose-500 hover:text-white focus:opacity-100"
                      title="Delete document"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
              {!filteredDocuments.length && (
                <tr>
                  <td className="px-3 py-8 text-center text-slate-500" colSpan={3}>
                    No matching documents.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
