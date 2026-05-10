import { useState } from 'react';
import axios from 'axios';
import { Play, Loader2, TrendingUp, TrendingDown, History, BarChart3, Target, Info, Coins, Calculator, ShieldCheck, Clock, DollarSign } from 'lucide-react';
import { API } from '../config';

interface BacktestResult {
  symbol: string;
  net_profit: number;
  roi_pct: number;
  max_drawdown: number;
  total_trades: number;
  win_rate: number;
  dca_added?: number;
  final_equity?: number;
}

export default function BacktestView() {
  const [mode, setMode] = useState<'standard' | 'dca'>('standard');
  const [symbol, setSymbol] = useState('XAUUSDm');
  const [days, setDays] = useState(365);
  const [balance, setBalance] = useState(10000);
  const [timeframe, setTimeframe] = useState('H1');
  const [risk, setRisk] = useState(2.0);
  const [dcaAmount, setDcaAmount] = useState(500);
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await axios.post(API.BOT.BACKTEST, { 
        type: mode,
        symbol, 
        days,
        balance,
        timeframe,
        risk,
        dca_amount: mode === 'dca' ? dcaAmount : undefined
      });
      if (res.data.status === 'success') {
        setResult(res.data.data);
      } else {
        setError(res.data.message || 'Failed to run backtest');
      }
    } catch (e) {
      if (axios.isAxiosError(e)) {
        setError(e.response?.data?.detail || e.message || 'Server error');
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="section-header justify-between">
        <div className="flex items-center gap-2">
          <span className="section-number">01</span>
          <span className="uppercase tracking-wider">Backtest Lab</span>
        </div>
        
        {/* Mode Switcher */}
        <div className="flex bg-white/5 p-1 rounded-xl border border-white/10">
          <button
            onClick={() => { setMode('standard'); setResult(null); }}
            className={`px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
              mode === 'standard' ? 'bg-[var(--color-primary)] text-slate-950 shadow-lg shadow-amber-500/20' : 'text-[var(--color-text-dim)] hover:text-white'
            }`}
          >
            Standard
          </button>
          <button
            onClick={() => { setMode('dca'); setResult(null); }}
            className={`px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
              mode === 'dca' ? 'bg-[var(--color-primary)] text-slate-950 shadow-lg shadow-amber-500/20' : 'text-[var(--color-text-dim)] hover:text-white'
            }`}
          >
            DCA Mode
          </button>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left: Configuration Panel */}
        <div className="lg:w-[40%] space-y-6">
          <div className="panel p-6 space-y-5">
            <div className="flex items-center gap-2 mb-2">
              {mode === 'standard' ? <Calculator size={16} className="text-[var(--color-primary)]" /> : <Coins size={16} className="text-[var(--color-primary)]" />}
              <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--color-text-primary)]">
                {mode === 'standard' ? 'Single Symbol Setup' : 'Unified DCA Setup'}
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Common Inputs */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider ml-1 flex items-center gap-1">
                  <DollarSign size={10} /> Initial Balance ($)
                </label>
                <input 
                  type="number"
                  value={balance}
                  onChange={(e) => setBalance(Number(e.target.value))}
                  className="w-full bg-[var(--color-bg-input)] border border-[var(--color-border-light)] rounded-xl px-4 py-3 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]/50 transition-all font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider ml-1 flex items-center gap-1">
                  <Clock size={10} /> Timeframe
                </label>
                <select 
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="w-full bg-[var(--color-bg-input)] border border-[var(--color-border-light)] rounded-xl px-4 py-3 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]/50 transition-all font-medium"
                >
                  <option value="M15">M15</option>
                  <option value="H1">H1</option>
                  <option value="H4">H4</option>
                  <option value="D1">D1</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider ml-1 flex items-center gap-1">
                  <ShieldCheck size={10} /> Risk per trade (%)
                </label>
                <input 
                  type="number"
                  step="0.1"
                  value={risk}
                  onChange={(e) => setRisk(Number(e.target.value))}
                  className="w-full bg-[var(--color-bg-input)] border border-[var(--color-border-light)] rounded-xl px-4 py-3 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]/50 transition-all font-mono"
                />
              </div>

              {/* Mode Specific Inputs */}
              {mode === 'standard' ? (
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider ml-1 flex items-center gap-1">
                    <Target size={10} /> Target Symbol
                  </label>
                  <select 
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="w-full bg-[var(--color-bg-input)] border border-[var(--color-border-light)] rounded-xl px-4 py-3 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]/50 transition-all font-medium"
                  >
                    <option value="XAUUSDm">XAUUSD (Gold)</option>
                    <option value="GBPUSDm">GBPUSD</option>
                    <option value="EURUSDm">EURUSD</option>
                    <option value="BTCUSDm">Bitcoin</option>
                  </select>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider ml-1 flex items-center gap-1">
                    <Coins size={10} /> Monthly DCA ($)
                  </label>
                  <input 
                    type="number"
                    value={dcaAmount}
                    onChange={(e) => setDcaAmount(Number(e.target.value))}
                    className="w-full bg-[var(--color-bg-input)] border border-amber-500/30 rounded-xl px-4 py-3 text-sm text-amber-400 outline-none focus:border-amber-500/50 transition-all font-mono"
                  />
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider ml-1">Lookback History</label>
              <div className="grid grid-cols-3 gap-2">
                {[180, 365, 730, 1095, 1825, 3650].map(d => (
                  <button
                    key={d}
                    onClick={() => setDays(d)}
                    className={`py-2.5 text-[10px] font-bold rounded-lg border transition-all ${
                      days === d 
                        ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-slate-950 shadow-lg shadow-amber-500/20' 
                        : 'bg-white/5 border-[var(--color-border-light)] text-[var(--color-text-dim)] hover:border-[var(--color-text-dim)]'
                    }`}
                  >
                    {d >= 365 ? `${(d/365).toFixed(0)} Year${d > 365 ? 's' : ''}` : `${d} Days`}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={runBacktest}
              disabled={loading}
              className="w-full btn btn-primary py-4 flex items-center justify-center gap-2 group shadow-xl shadow-amber-500/10"
            >
              {loading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  <span>Calculating {mode.toUpperCase()}...</span>
                </>
              ) : (
                <>
                  <Play size={18} className="group-hover:translate-x-0.5 transition-transform" />
                  <span>Execute {mode.toUpperCase()}</span>
                </>
              )}
            </button>

            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium animate-shake">
                {error}
              </div>
            )}
          </div>

          <div className="panel p-5 bg-blue-500/5 border-blue-500/10">
            <div className="flex items-start gap-3">
              <Info size={16} className="text-blue-400 mt-0.5" />
              <div className="space-y-1">
                <h4 className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                  {mode === 'dca' ? 'Dynamic Portfolio Simulation' : 'Single Asset Analysis'}
                </h4>
                <p className="text-[11px] text-[var(--color-text-dim)] leading-relaxed">
                  {mode === 'dca' 
                    ? 'In DCA Mode, all strategy parameters (TF, Risk) apply to ALL symbols simultaneously. Monthly deposits compound the equity curve.' 
                    : 'Standard mode isolates your strategy on a single symbol with static initial capital.'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Results Panel */}
        <div className="lg:w-[60%]">
          {!result && !loading && (
            <div className="panel h-full flex flex-col items-center justify-center p-12 text-center space-y-4 min-h-[400px]">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center text-[var(--color-text-dim)]">
                {mode === 'dca' ? <Coins size={32} /> : <BarChart3 size={32} />}
              </div>
              <div className="max-w-xs">
                <h3 className="text-base font-bold text-[var(--color-text-primary)] mb-1">
                  {mode === 'dca' ? 'Unified Strategy Tester' : 'Asset Focus Lab'}
                </h3>
                <p className="text-xs text-[var(--color-text-dim)]">
                  {mode === 'dca' 
                    ? 'Simulate long-term wealth building with custom risk and timeframe across your portfolio.' 
                    : 'Test your logic on specific market conditions with fixed capital.'}
                </p>
              </div>
            </div>
          )}

          {loading && (
            <div className="panel h-full flex flex-col items-center justify-center p-12 min-h-[400px] space-y-6">
              <div className="relative">
                <div className="w-20 h-20 rounded-full border-2 border-[var(--color-primary)]/20 border-t-[var(--color-primary)] animate-spin" />
                <History className="absolute inset-0 m-auto text-[var(--color-primary)] animate-pulse" size={24} />
              </div>
              <div className="text-center">
                <h3 className="text-base font-bold text-[var(--color-text-primary)] mb-1">Simulating History</h3>
                <p className="text-xs text-[var(--color-text-dim)]">
                  Running across enabled symbols with TF: {timeframe} and Risk: {risk}%...
                </p>
              </div>
            </div>
          )}

          {result && (
            <div className="space-y-6 animate-fadeInUp">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="panel p-6 bg-gradient-to-br from-emerald-500/10 to-transparent border-emerald-500/20">
                  <div className="flex justify-between items-start mb-4">
                    <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
                      <TrendingUp size={20} />
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider">Growth Ratio</div>
                      <div className="text-lg font-bold text-emerald-400">+{result.roi_pct}%</div>
                    </div>
                  </div>
                  <div className="text-[10px] font-bold text-emerald-500/70 uppercase tracking-widest mb-1">Total Net Profit</div>
                  <div className="text-4xl font-extrabold text-number text-white">
                    ${result.net_profit.toLocaleString()}
                  </div>
                </div>

                <div className="panel p-6 bg-gradient-to-br from-rose-500/10 to-transparent border-rose-500/20">
                  <div className="flex justify-between items-start mb-4">
                    <div className="p-2 rounded-lg bg-rose-500/20 text-rose-400">
                      <TrendingDown size={20} />
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider">Risk Sensitivity</div>
                      <div className={`text-lg font-bold ${result.max_drawdown < 15 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {result.max_drawdown < 15 ? 'Stable' : 'Aggressive'}
                      </div>
                    </div>
                  </div>
                  <div className="text-[10px] font-bold text-rose-500/70 uppercase tracking-widest mb-1">Max Drawdown</div>
                  <div className="text-4xl font-extrabold text-number text-white">
                    {result.max_drawdown}%
                  </div>
                </div>

                {mode === 'dca' ? (
                  <div className="panel p-6 border-amber-500/20 bg-amber-500/5">
                    <div className="flex items-center gap-4">
                      <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400">
                        <Coins size={20} />
                      </div>
                      <div>
                        <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider">Capital Added (DCA)</div>
                        <div className="text-2xl font-bold text-number text-white">${result.dca_added?.toLocaleString()}</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="panel p-6">
                    <div className="flex items-center gap-4">
                      <div className="p-2 rounded-lg bg-[var(--color-primary)]/20 text-[var(--color-primary)]">
                        <Target size={20} />
                      </div>
                      <div>
                        <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider">Win Rate</div>
                        <div className="text-2xl font-bold text-number text-white">{result.win_rate}%</div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="panel p-6 border-white/10 bg-white/5">
                  <div className="flex items-center gap-4">
                    <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400">
                      <BarChart3 size={20} />
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-wider">Final Equity</div>
                      <div className="text-2xl font-bold text-number text-[var(--color-primary)]">${result.final_equity?.toLocaleString() || 'N/A'}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="panel p-8 bg-[var(--color-primary)] shadow-2xl shadow-amber-500/20 text-slate-950">
                <div className="flex flex-col sm:flex-row justify-between items-center gap-6">
                  <div className="space-y-1 text-center sm:text-left">
                    <h3 className="text-xl font-black uppercase tracking-tight">
                      {mode === 'dca' ? 'Wealth Multiplier Active' : 'Strategy Logic Verified'}
                    </h3>
                    <p className="text-xs font-bold opacity-80 uppercase tracking-widest">
                      {mode === 'dca' ? 'Portfolio projection based on recurring deposits.' : 'Strategy performance within historical norms.'}
                    </p>
                  </div>
                  <div className="px-6 py-2 bg-slate-950 text-amber-400 rounded-full text-[10px] font-black uppercase tracking-[0.2em] shadow-xl">
                    Berserker v3.0
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
