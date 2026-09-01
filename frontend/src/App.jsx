import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useLiveQuery } from "dexie-react-hooks";
import { db } from "./db";
import Header from "./components/Header";
import AudioPlayer from "./components/AudioPlayer";
import DocumentUploader from "./components/DocumentUploader";
import DocumentList from "./components/DocumentList";
import ReaderMode from "./components/ReaderMode";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const statusStyles = {
  uploaded: "bg-slate-700 text-slate-100",
  extracting: "bg-amber-600 text-amber-50",
  extracted: "bg-cyan-700 text-cyan-50",
  completed: "bg-emerald-700 text-emerald-50",
  failed: "bg-rose-700 text-rose-50"
};

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Request failed (${response.status})`);
    }
    throw new Error(data.detail || `Request failed (${response.status})`);
  }
  return await response.json();
}

export default function App() {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [message, setMessage] = useState("Ready.");
  const [selectedVoice, setSelectedVoice] = useState("en-NG-AbeoNeural");
  const [voiceOptions, setVoiceOptions] = useState([]);
  
  const [readerDocumentId, setReaderDocumentId] = useState("");
  const [selectedSectionByDocument, setSelectedSectionByDocument] = useState({});
  const [isReaderPlaying, setIsReaderPlaying] = useState(false);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [activeReadingKey, setActiveReadingKey] = useState(null);
  
  const sectionAudioRef = useRef(null);
  

  const lastObjectUrlRef = useRef(null);
  const inFlightRef = useRef(new Set());

  const documents = useLiveQuery(() => db.documents.orderBy('createdAt').reverse().toArray()) || [];

  const filteredDocuments = useMemo(() => {
    if (statusFilter === "all") return documents;
    return documents.filter((document) => document.status === statusFilter);
  }, [documents, statusFilter]);

  const seekableDocuments = useMemo(() => documents.filter((doc) => !!doc.text), [documents]);

  const readerDocument = useMemo(
    () => documents.find((doc) => String(doc.id) === String(readerDocumentId)) || null,
    [documents, readerDocumentId]
  );
  
  const readerSections = useMemo(() => {
    if (!readerDocument) return [];
    return Array.isArray(readerDocument.chapters) ? readerDocument.chapters : [];
  }, [readerDocument]);

  const activeTitle = useMemo(() => {
    if (!activeReadingKey || !readerDocumentId) return null;
    const [docId, secIndex] = activeReadingKey.split(':');
    if (String(docId) !== String(readerDocumentId)) return null;
    const section = readerSections.find(s => String(s.index) === secIndex);
    return section ? (section.title || `Section ${Number(secIndex) + 1}`) : null;
  }, [activeReadingKey, readerSections, readerDocumentId]);

  const activeReaderSection = useMemo(() => {
    if (!readerDocument || !readerSections.length) return null;
    const selectedIndex = selectedSectionByDocument[readerDocument.id];
    if (selectedIndex === undefined || selectedIndex === null) return readerSections[0];
    return readerSections.find((s) => Number(s.index) === Number(selectedIndex)) || readerSections[0];
  }, [readerDocument, readerSections, selectedSectionByDocument]);

  useEffect(() => {
    if (!readerDocumentId && documents.length > 0) {
      setReaderDocumentId(String(documents[0].id));
    }
  }, [documents, readerDocumentId]);

  useEffect(() => {
    async function loadVoices() {
      try {
        const data = await fetchJson("/voices/");
        if (data && data.voices) setVoiceOptions(data.voices);
      } catch (e) {
        setVoiceOptions([
          { value: "en-US-AriaNeural", label: "US English - Aria" },
          { value: "en-NG-AbeoNeural", label: "Nigerian English - Abeo" },
          { value: "en-NG-EzinneNeural", label: "Nigerian English - Ezinne" }
        ]);
      }
    }
    loadVoices();
  }, []);

  useEffect(() => {
    const audioNode = sectionAudioRef.current;
    if (!audioNode) return;
    const onEnded = () => { setIsReaderPlaying(false); setActiveReadingKey(null); };
    const onPause = () => setIsReaderPlaying(false);
    const onPlay = () => setIsReaderPlaying(true);
    audioNode.addEventListener("ended", onEnded);
    audioNode.addEventListener("pause", onPause);
    audioNode.addEventListener("play", onPlay);
    return () => {
      audioNode.removeEventListener("ended", onEnded);
      audioNode.removeEventListener("pause", onPause);
      audioNode.removeEventListener("play", onPlay);
    };
  }, [sectionAudioRef.current]);

  async function handleUpload(event) {
    event.preventDefault();
    if (!file) {
      setMessage("Select a PDF file to upload.");
      return;
    }

    const resolvedTitle = title.trim() || file.name.replace(/\.pdf$/i, "").trim() || "Untitled PDF";
    const payload = new FormData();
    payload.append("source_file", file);

    setIsUploading(true);
    setMessage("Uploading and extracting text...");
    
    let docId = null;
    try {
      docId = await db.documents.add({
        title: resolvedTitle,
        status: "extracting",
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });

      const extractData = await fetchJson("/extract/", { method: "POST", body: payload });
      const extractedText = extractData.text;

      await db.documents.update(docId, {
        text: extractedText,
        status: "extracted",
        updatedAt: Date.now()
      });
      setMessage("Text extracted. Intelligently detecting chapters and summary...");

      const aiData = await fetchJson("/ai/sections/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: extractedText })
      });

      await db.documents.update(docId, {
        chapters: aiData.chapters || [],
        ai_summary: aiData.summary || "No summary available.",
        ai_provider: aiData.provider || "heuristic",
        ai_anchored: Boolean(aiData.ai_anchored),
        status: "completed",
        updatedAt: Date.now()
      });

      setMessage("Document processing complete.");
      setTitle("");
      setFile(null);
    } catch (error) {
      if (docId) await db.documents.update(docId, { status: "failed", updatedAt: Date.now() });
      setMessage(`Processing failed: ${error.message}`);
    } finally {
      setIsUploading(false);
    }
  }

  async function deleteDocument(documentId) {
    try {
      await db.documents.delete(documentId);
      await db.audio_chunks.where("documentId").equals(String(documentId)).delete();
      setMessage("Document deleted from local storage.");
      if (Number(readerDocumentId) === Number(documentId)) {
        setReaderDocumentId("");
      }
    } catch (error) {
      setMessage(`Delete failed: ${error.message}`);
    }
  }

  function selectReaderSection(documentId, sectionIndex) {
    setSelectedSectionByDocument((prev) => ({ ...prev, [documentId]: sectionIndex }));
  }

  // Background pre-cacher: once a document is open, quietly synthesize and save
  // each section's audio for the selected voice, one at a time. By the time the
  // reader reaches a section it's already on the device, so playback is instant
  // and the whole book becomes available offline after one pass.
  useEffect(() => {
    if (!readerDocument || !readerSections.length) return;
    let cancelled = false;

    (async () => {
      // Small head start so we don't compete with an immediate "Read Now".
      await new Promise((resolve) => setTimeout(resolve, 400));
      for (const section of readerSections) {
        if (cancelled) return;
        try {
          await ensureSectionCached(readerDocument.id, section, selectedVoice);
        } catch {
          /* leave it for on-demand synthesis when the user opens it */
        }
        await new Promise((resolve) => setTimeout(resolve, 150));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [readerDocument, readerSections, selectedVoice]);

  // Find a cached clip for this exact section AND voice (voice is not indexed,
  // so filter it in memory over the documentId index).
  async function findCachedChunk(documentId, sectionIndex, voice) {
    return db.audio_chunks
      .where("documentId")
      .equals(String(documentId))
      .and((chunk) => Number(chunk.sectionIndex) === Number(sectionIndex) && chunk.voice === voice)
      .first();
  }

  async function playBlob(blob) {
    if (!sectionAudioRef.current) sectionAudioRef.current = new Audio();
    const audioNode = sectionAudioRef.current;
    // Release the previous object URL so blobs don't leak across plays.
    if (lastObjectUrlRef.current) {
      URL.revokeObjectURL(lastObjectUrlRef.current);
    }
    const objectUrl = URL.createObjectURL(blob);
    lastObjectUrlRef.current = objectUrl;
    audioNode.src = objectUrl;
    await audioNode.play();
    setIsReaderPlaying(true);
  }

  // Return the audio blob for a section+voice, synthesizing and saving it to the
  // device on a cache miss. An in-flight guard means the background pre-cacher
  // and a user's "Read Now" never synthesize the same clip twice.
  async function ensureSectionCached(documentId, section, voice) {
    const cached = await findCachedChunk(documentId, section.index, voice);
    if (cached) return cached.audioBlob;

    const key = `${documentId}:${section.index}:${voice}`;
    if (inFlightRef.current.has(key)) {
      for (let i = 0; i < 60 && inFlightRef.current.has(key); i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
      const settled = await findCachedChunk(documentId, section.index, voice);
      if (settled) return settled.audioBlob;
    }

    inFlightRef.current.add(key);
    try {
      const response = await fetch(`${API_BASE_URL}/tts/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: section.text, voice })
      });
      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          detail = (await response.json()).detail || detail;
        } catch {
          /* non-JSON error body */
        }
        throw new Error(detail);
      }
      const blob = await response.blob();
      // Keep one clip per section (drop any previous-voice clip first).
      await db.audio_chunks
        .where("documentId")
        .equals(String(documentId))
        .and((chunk) => Number(chunk.sectionIndex) === Number(section.index))
        .delete();
      await db.audio_chunks.add({
        documentId: String(documentId),
        sectionIndex: Number(section.index),
        voice,
        audioBlob: blob,
        createdAt: Date.now()
      });
      return blob;
    } finally {
      inFlightRef.current.delete(key);
    }
  }

  async function readSection(documentId, sectionIndex) {
    const section = readerSections.find((s) => Number(s.index) === Number(sectionIndex));
    if (!section || !section.text) {
      setMessage("No text available for this section.");
      return;
    }

    const sectionKey = `${documentId}:${sectionIndex}`;
    setActiveReadingKey(sectionKey);
    setIsLoadingAudio(true);
    const readingTitle = section.title || `Section ${sectionIndex + 1}`;

    try {
      const alreadySaved = await findCachedChunk(documentId, sectionIndex, selectedVoice);
      setMessage(alreadySaved ? `Now playing (saved on device): ${readingTitle}...` : `Preparing ${readingTitle}...`);
      const blob = await ensureSectionCached(documentId, section, selectedVoice);
      setMessage(`Now playing: ${readingTitle}.`);
      await playBlob(blob);
    } catch (error) {
      setMessage(`Read section failed: ${error.message}`);
      setActiveReadingKey(null);
    } finally {
      setIsLoadingAudio(false);
    }
  }

  async function toggleReaderPlayback() {
    const audioNode = sectionAudioRef.current;
    if (!audioNode || !audioNode.src) {
      setMessage("Select a section and tap Read Now first.");
      return;
    }
    if (audioNode.paused) {
      try {
        await audioNode.play();
        setIsReaderPlaying(true);
        setMessage("Playback resumed.");
      } catch {
        setMessage("Unable to resume playback.");
      }
    } else {
      audioNode.pause();
      setIsReaderPlaying(false);
      setMessage("Playback paused.");
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-36 relative overflow-hidden font-sans">
      <div className="absolute top-0 inset-x-0 h-96 bg-gradient-to-b from-brand-900/20 to-transparent pointer-events-none"></div>
      
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-12 md:px-8 relative z-10">
        <Header />
        
        <div className="flex flex-col gap-8 lg:flex-row mt-6">
          <DocumentUploader
            title={title}
            setTitle={setTitle}
            file={file}
            setFile={setFile}
            isUploading={isUploading}
            message={message}
            handleUpload={handleUpload}
          />

          <DocumentList
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            filteredDocuments={filteredDocuments}
            deleteDocument={deleteDocument}
            statusStyles={statusStyles}
          />
        </div>

        <div className="mt-4">
          <ReaderMode
            selectedVoice={selectedVoice}
            setSelectedVoice={setSelectedVoice}
            voiceOptions={voiceOptions}
            readerDocumentId={readerDocumentId}
            setReaderDocumentId={setReaderDocumentId}
            seekableDocuments={seekableDocuments}
            readerSections={readerSections}
            activeReaderSection={activeReaderSection}
            selectReaderSection={selectReaderSection}
            readSection={readSection}
            isLoadingAudio={isLoadingAudio}
            readerDocument={readerDocument}
          />
        </div>
      </div>
      
      <AudioPlayer 
        audioRef={sectionAudioRef}
        title={activeTitle}
        isPlaying={isReaderPlaying}
        onTogglePlay={toggleReaderPlayback}
      />
    </div>
  );
}
