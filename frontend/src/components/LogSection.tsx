import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { Terminal, ArrowDown, PowerOff, ShieldAlert } from 'lucide-react';
import { API } from '../config';

interface Props {
  apiOnline: boolean;
  botRunning: boolean;
}

function colorizeLog(line: string): string {
  if (line.includes('SYSTEM')) return 'log-system';
  if (line.includes('ERROR') || line.includes('CRITICAL')) return 'log-error';
  if (line.includes('WARNING') || line.includes('WARN')) return 'log-warn';
  if (line.includes('EXECUTED') || line.includes('SUCCESS') || line.includes('CONNECTED')) return 'log-success';
  if (line.includes('INFO')) return 'log-info';
  return 'log-default';
}

export default function LogSection({ apiOnline, botRunning }: Props) {
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    if (!apiOnline) return;
    try {
      const res = await axios.get(`${API.MONITOR.LOGS}?lines=80`, { timeout: 3000 });
      setLogs(res.data.logs || []);
    } catch {
      // silent
    }
  }, [apiOnline]);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 60);
  };

  return (
    <section className="animate-fadeInUp" style={{ animationDelay: '200ms' }}>
      <div className="section-header justify-between">
        <div className="flex items-center gap-2">
          <span className="section-number">03</span>
          <span className="uppercase tracking-wider">Live Engine Logs</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-[var(--color-text-dim)] font-mono">
            {logs.length} lines
          </span>
          {!autoScroll && (
            <button
              onClick={() => {
                setAutoScroll(true);
                if (containerRef.current) {
                  containerRef.current.scrollTop = containerRef.current.scrollHeight;
                }
              }}
              className="flex items-center gap-1 text-[10px] text-[var(--color-accent)] hover:text-[var(--color-text-primary)] transition-colors font-semibold"
            >
              <ArrowDown size={10} /> Auto-scroll
            </button>
          )}
        </div>
      </div>

      <div className="panel overflow-hidden relative">
        <div className="px-4 py-2.5 border-b border-[var(--color-border-subtle)] flex items-center gap-2 bg-white/[0.01]">
          <Terminal size={14} className={botRunning ? 'text-emerald-400' : 'text-[var(--color-text-dim)]'} />
          <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-wider">
            Execution Stream
          </span>
          <div className="ml-auto flex items-center gap-2">
             <span className={`text-[8px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded ${
               botRunning ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
             }`}>
               {botRunning ? 'Streaming' : 'Paused'}
             </span>
             <div className={`w-1.5 h-1.5 rounded-full ${botRunning ? 'bg-emerald-400 animate-pulse-dot' : 'bg-rose-500/50'}`} />
          </div>
        </div>

        <div
          ref={containerRef}
          onScroll={handleScroll}
          className={`h-[320px] overflow-y-auto p-4 font-mono text-[12px] leading-relaxed transition-opacity duration-500 ${!botRunning ? 'opacity-60' : 'opacity-100'}`}
          style={{ background: 'rgba(4, 6, 12, 0.6)' }}
        >
          {logs.length === 0 ? (
            <div className="text-[var(--color-text-dim)] italic text-center py-12">
              {apiOnline ? 'Waiting for engine logs...' : 'API offline — cannot fetch logs'}
            </div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className={`py-0.5 whitespace-pre-wrap break-all ${colorizeLog(log)}`}>
                {log}
              </div>
            ))
          )}
        </div>

        {/* Stopped Overlay Indicator */}
        {!botRunning && logs.length > 0 && (
          <div className="absolute inset-0 top-[40px] pointer-events-none flex flex-col items-center justify-center bg-slate-950/20 backdrop-blur-[1px]">
             <div className="px-4 py-2 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2 text-rose-400 text-[10px] font-black uppercase tracking-widest shadow-2xl">
                <PowerOff size={12} />
                Engine Halted — No new logs incoming
             </div>
          </div>
        )}

        {/* Empty Log Warning */}
        {logs.length === 0 && !botRunning && (
          <div className="absolute inset-0 top-[40px] flex flex-col items-center justify-center p-8 text-center space-y-3">
             <ShieldAlert size={24} className="text-rose-500/50" />
             <p className="text-xs text-[var(--color-text-dim)] max-w-[200px]">
               The trading engine is not running. Start the engine to see live logs.
             </p>
          </div>
        )}
      </div>

      <style>{`
        .log-system { color: #38bdf8; font-weight: 700; border-left: 2px solid #38bdf8; padding-left: 8px; margin: 4px 0; background: rgba(56, 189, 248, 0.05); }
        .log-error { color: #f87171; font-weight: 600; }
        .log-warn { color: #fbbf24; }
        .log-success { color: #34d399; }
        .log-info { color: #94a3b8; }
        .log-default { color: #64748b; }
      `}</style>
    </section>
  );
}
