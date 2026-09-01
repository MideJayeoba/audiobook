import { useEffect, useState } from "react";

function formatTime(seconds) {
  if (isNaN(seconds) || !isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function AudioPlayer({ audioRef, title, isPlaying, onTogglePlay }) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isSeeking, setIsSeeking] = useState(false);

  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  useEffect(() => {
    const audio = audioRef?.current;
    if (!audio) return;

    const updateTime = () => {
      if (!isSeeking) setCurrentTime(audio.currentTime);
    };
    const updateDuration = () => setDuration(audio.duration);

    audio.addEventListener("timeupdate", updateTime);
    audio.addEventListener("loadedmetadata", updateDuration);

    // Initial sync
    setCurrentTime(audio.currentTime || 0);
    setDuration(audio.duration || 0);

    return () => {
      audio.removeEventListener("timeupdate", updateTime);
      audio.removeEventListener("loadedmetadata", updateDuration);
    };
  }, [audioRef, isSeeking]);

  useEffect(() => {
    if (audioRef?.current) {
      audioRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed, title, isPlaying]);

  const handleSeekChange = (e) => {
    setIsSeeking(true);
    setCurrentTime(Number(e.target.value));
  };

  const handleSeekCommit = (e) => {
    const time = Number(e.target.value);
    if (audioRef?.current) {
      audioRef.current.currentTime = time;
    }
    setIsSeeking(false);
  };

  const handleSkip = (amount) => {
    if (audioRef?.current) {
      const audio = audioRef.current;
      const newTime = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + amount));
      audio.currentTime = newTime;
      setCurrentTime(newTime);
    }
  };

  const handleSpeedChange = () => {
    const speeds = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];
    const nextSpeed = speeds[(speeds.indexOf(playbackSpeed) + 1) % speeds.length];
    setPlaybackSpeed(nextSpeed);
  };

  if (!title) return null; // Hide if nothing is selected/playing

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[95%] max-w-2xl">
      <div className="flex flex-col items-center justify-center rounded-[2rem] border border-slate-700/50 bg-slate-900/80 p-4 pb-5 backdrop-blur-2xl shadow-[0_20px_50px_-12px_rgba(0,0,0,0.6)] animate-slide-up group">
        
        {/* Glow effect */}
        <div className="absolute inset-0 rounded-[2rem] bg-gradient-to-r from-brand-500/5 via-transparent to-brand-500/5 opacity-50 group-hover:opacity-100 transition-opacity pointer-events-none"></div>
        
        <div className="w-full flex flex-col gap-4 relative z-10">
          <div className="flex items-center justify-between px-4 text-sm mt-1">
            <span className="font-semibold text-white truncate pr-4 text-base tracking-tight">{title}</span>
            <span className="text-brand-300 font-mono text-xs tabular-nums shrink-0 bg-brand-500/10 px-2.5 py-1 rounded-lg border border-brand-500/20">
              {formatTime(currentTime)} <span className="text-slate-500 mx-1">/</span> {formatTime(duration)}
            </span>
          </div>

          <div className="flex w-full items-center px-4">
            <div className="relative w-full h-2 group/slider flex items-center">
              <input
                type="range"
                min={0}
                max={duration || 100}
                value={currentTime}
                onChange={handleSeekChange}
                onMouseUp={handleSeekCommit}
                onTouchEnd={handleSeekCommit}
                className="absolute w-full h-1.5 cursor-pointer appearance-none rounded-full bg-slate-800/80 outline-none transition-all focus:ring-2 focus:ring-brand-500/30 group-hover/slider:h-2 z-10 opacity-0"
              />
              {/* Custom Track */}
              <div className="w-full h-1.5 bg-slate-800/80 rounded-full overflow-hidden absolute pointer-events-none group-hover/slider:h-2 transition-all">
                <div 
                  className="h-full bg-brand-500 relative" 
                  style={{ width: `${(currentTime / (duration || 1)) * 100}%` }}
                >
                  <div className="absolute right-0 top-0 bottom-0 w-4 bg-gradient-to-l from-white/30 to-transparent"></div>
                </div>
              </div>
              {/* Custom Thumb */}
              <div 
                className="absolute w-3 h-3 bg-white rounded-full shadow-[0_0_10px_rgba(16,185,129,0.8)] pointer-events-none transform -translate-x-1/2 scale-0 group-hover/slider:scale-100 transition-transform z-20"
                style={{ left: `${(currentTime / (duration || 1)) * 100}%` }}
              ></div>
            </div>
          </div>

          <div className="flex items-center justify-center gap-8 relative w-full px-4">
            <button onClick={() => handleSkip(-15)} className="text-slate-400 hover:text-brand-400 transition-all hover:scale-110 active:scale-95 p-3 rounded-full hover:bg-slate-800/50" title="Rewind 15s">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/></svg>
            </button>
            
            <button
              onClick={onTogglePlay}
              className="group/btn flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-tr from-brand-600 to-brand-400 text-white transition-all hover:scale-105 active:scale-95 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] border border-white/10"
            >
              {isPlaying ? (
                <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" className="transition-transform group-hover/btn:scale-110"><path d="M6 4h4v16H6zm8 0h4v16h-4z"/></svg>
              ) : (
                <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" className="ml-1 transition-transform group-hover/btn:scale-110"><path d="M8 5v14l11-7z"/></svg>
              )}
            </button>

            <button onClick={() => handleSkip(15)} className="text-slate-400 hover:text-brand-400 transition-all hover:scale-110 active:scale-95 p-3 rounded-full hover:bg-slate-800/50" title="Skip 15s">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M13 17l5-5-5-5M6 17l5-5-5-5"/></svg>
            </button>
            
            <button 
              onClick={handleSpeedChange} 
              className="absolute right-4 text-xs font-semibold text-slate-400 hover:text-brand-400 transition-colors bg-slate-800/50 hover:bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700/50 shadow-sm"
              title="Playback Speed"
            >
              {playbackSpeed}x
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
