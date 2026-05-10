import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Activity, Clock, Settings, LayoutDashboard, History, Terminal, Zap, ShieldAlert, Cpu } from 'lucide-react';
import { API } from './config';
import LiveView from './components/LiveView';
import BacktestView from './components/BacktestView';
import SettingsModal from './components/SettingsModal';

// --- TITAN SECURITY LAYER: Global API Key Injection ---
axios.interceptors.request.use((config) => {
  if (config.url?.startsWith(API.BASE)) {
    config.headers[API.HEADER] = API.KEY;
  }
  return config;
});

interface BotStatus {
  running: boolean;
}

function App() {
  const [view, setView] = useState<'live' | 'backtest'>('live');
  const [status, setStatus] = useState<BotStatus>({ running: false });
  const [apiOnline, setApiOnline] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [lastSync, setLastSync] = useState('—');
  const [toggling, setToggling] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get<BotStatus>(API.BOT.STATUS, { timeout: 3000 });
      setStatus(res.data);
      setApiOnline(true);
      setLastSync(new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch {
      setApiOnline(false);
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(fetchStatus, 3000); // Faster refresh for status
    
    // Initial fetch wrapped to avoid synchronous setState warning
    const init = async () => {
      await fetchStatus();
    };
    init();

    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleToggleBot = async () => {
    setToggling(true);
    try {
      if (status.running) {
        await axios.post(API.BOT.STOP);
      } else {
        await axios.post(API.BOT.START, { mode: 'live' });
      }
      setTimeout(fetchStatus, 800);
    } catch (e) {
      console.error('Toggle bot error:', e);
    } finally {
      setToggling(false);
    }
  };

  return (
    <div className={`flex min-h-screen bg-[var(--color-bg-base)] text-[var(--color-text-primary)] transition-all duration-700 ${status.running ? 'border-l-4 border-emerald-500/30' : 'border-l-4 border-rose-500/10'}`}>
      {/* ─── Sidebar ─── */}
      <aside className="w-20 lg:w-64 border-r border-[var(--color-border-subtle)] flex flex-col fixed inset-y-0 z-[60] bg-[var(--color-bg-base)] shadow-2xl">
        <div className="p-6 flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-slate-950 flex-shrink-0 transition-all duration-500 ${
            status.running ? 'bg-emerald-400 shadow-[0_0_20px_rgba(52,211,153,0.4)] animate-pulse' : 'bg-gradient-to-br from-amber-400 to-orange-600 shadow-[0_0_20px_rgba(245,158,11,0.2)]'
          }`}>
            <Zap size={22} strokeWidth={2.5} />
          </div>
          <div className="hidden lg:block overflow-hidden whitespace-nowrap">
            <h1 className="font-black text-lg tracking-tight text-glow-gold">TITAN</h1>
            <p className="text-[9px] text-[var(--color-accent)] font-mono uppercase tracking-[0.2em] font-black">Berserker v3.0</p>
          </div>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2">
          <button
            onClick={() => setView('live')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              view === 'live' 
                ? 'bg-white/10 text-white shadow-xl' 
                : 'text-[var(--color-text-dim)] hover:bg-white/5 hover:text-white'
            }`}
          >
            <LayoutDashboard size={20} className={view === 'live' ? 'text-[var(--color-primary)]' : ''} />
            <span className="hidden lg:block text-xs font-bold uppercase tracking-wider">Live Trading</span>
          </button>
          
          <button
            onClick={() => setView('backtest')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              view === 'backtest' 
                ? 'bg-white/10 text-white shadow-xl' 
                : 'text-[var(--color-text-dim)] hover:bg-white/5 hover:text-white'
            }`}
          >
            <History size={20} className={view === 'backtest' ? 'text-[var(--color-primary)]' : ''} />
            <span className="hidden lg:block text-xs font-bold uppercase tracking-wider">Backtest Lab</span>
          </button>
        </nav>

        {/* Engine Status Card */}
        <div className="px-4 py-6 border-t border-[var(--color-border-subtle)] space-y-4">
          <div className={`hidden lg:block p-4 rounded-2xl border transition-all duration-500 ${
            status.running 
              ? 'bg-emerald-500/10 border-emerald-500/30 shadow-[0_0_20px_rgba(16,185,129,0.05)]' 
              : 'bg-rose-500/5 border-rose-500/20'
          }`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[9px] font-black uppercase tracking-[0.2em] text-[var(--color-text-dim)]">System Core</span>
              <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${
                status.running ? 'bg-emerald-400 text-slate-950 animate-pulse' : 'bg-rose-500 text-white'
              }`}>
                {status.running ? 'Active' : 'Standby'}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${status.running ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                {status.running ? <Cpu size={16} className="animate-spin-slow" /> : <ShieldAlert size={16} />}
              </div>
              <div className="overflow-hidden">
                <p className="text-[11px] font-bold text-white truncate">{status.running ? 'Engine Running' : 'Engine Halted'}</p>
                <p className="text-[9px] text-[var(--color-text-dim)] font-medium">Mode: Production</p>
              </div>
            </div>
          </div>

          <button
            onClick={() => setShowSettings(true)}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-[var(--color-text-dim)] hover:bg-white/5 hover:text-white transition-all group"
          >
            <Settings size={20} className="group-hover:rotate-45 transition-transform duration-500" />
            <span className="hidden lg:block text-xs font-bold uppercase tracking-wider">Settings</span>
          </button>
          
          <div className="hidden lg:block px-4 py-2">
             <div className="flex items-center justify-between">
                <span className="text-[9px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider">API Connection</span>
                <span className={`text-[9px] font-mono ${apiOnline ? 'text-emerald-400' : 'text-rose-500'}`}>
                  {apiOnline ? 'ONLINE' : 'OFFLINE'}
                </span>
             </div>
          </div>
        </div>
      </aside>

      {/* ─── Main Content ─── */}
      <div className="flex-1 ml-20 lg:ml-64 flex flex-col min-h-screen">
        {/* Header */}
        <header className="h-[72px] border-b border-[var(--color-border-subtle)] sticky top-0 z-50 bg-[var(--color-bg-base)]/80 backdrop-blur-xl px-6 lg:px-10 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--color-text-muted)] flex items-center gap-3">
              {view === 'live' ? 'Dashboard Overview' : 'Strategy Research'}
              {status.running && view === 'live' && (
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-black animate-fadeIn">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  LIVE
                </span>
              )}
            </h2>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 text-[var(--color-text-muted)] px-3 py-1.5 rounded-full border border-[var(--color-border-subtle)] bg-white/[0.02]">
              <Clock size={12} className={apiOnline ? 'text-amber-400' : 'text-[var(--color-text-dim)]'} />
              <span className="text-[11px] font-mono font-medium">{lastSync}</span>
            </div>

            <button
              onClick={handleToggleBot}
              disabled={toggling || !apiOnline}
              className={`btn relative overflow-hidden h-10 px-8 rounded-xl text-xs font-black uppercase tracking-[0.15em] transition-all duration-500 shadow-2xl ${
                status.running 
                  ? 'bg-rose-500 text-white shadow-rose-500/20 hover:scale-[1.02] active:scale-95' 
                  : 'bg-emerald-500 text-slate-950 shadow-emerald-500/20 hover:scale-[1.02] active:scale-95'
              } disabled:opacity-30`}
            >
              <div className="flex items-center gap-2 relative z-10">
                {status.running ? <Terminal size={14} /> : <Activity size={14} />}
                {toggling ? 'WAIT...' : status.running ? 'Stop Engine' : 'Engage Live'}
              </div>
              {status.running && (
                <div className="absolute inset-0 bg-white/10 animate-pulse" />
              )}
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="p-6 lg:p-10 max-w-[1440px]">
          {view === 'live' ? <LiveView apiOnline={apiOnline} botRunning={status.running} /> : <BacktestView />}
        </main>

        {/* Footer */}
        <footer className="mt-auto px-6 lg:px-10 py-6 border-t border-[var(--color-border-subtle)] flex flex-col sm:flex-row justify-between items-center gap-4">
          <span className="text-[11px] text-[var(--color-text-dim)] font-medium">TITAN Berserker Trading Engine © {new Date().getFullYear()}</span>
          <div className="flex items-center gap-6 text-[10px] text-[var(--color-text-dim)] font-black uppercase tracking-widest">
            <span className="hover:text-white cursor-help transition-colors">Documentation</span>
            <span className="hover:text-white cursor-help transition-colors">System Health</span>
          </div>
        </footer>
      </div>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      
      {/* Global pulse effect when running */}
      <style>{`
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .animate-spin-slow {
          animation: spin-slow 8s linear infinite;
        }
      `}</style>
    </div>
  );
}

export default App;
