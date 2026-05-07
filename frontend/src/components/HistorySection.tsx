import { Search, RefreshCw } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../config';

interface Trade {
  time: string;
  symbol: string;
  strategy: string;
  pnl: number;
  balance: number;
}

export default function HistorySection() {
  const [search, setSearch] = useState('');
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchTrades = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<Trade[]>(API.MONITOR.TRADES, { timeout: 5000 });
      setTrades(res.data);
    } catch (e) {
      console.error('Failed to fetch trades:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchTrades]);

  const filtered = trades.filter(row =>
    !search || Object.values(row).some(v => String(v).toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <section className="animate-fadeInUp" style={{ animationDelay: '300ms' }}>
      <div className="section-header justify-between">
        <div className="flex items-center gap-2">
          <span className="section-number">04</span>
          <span className="uppercase tracking-wider">Trade History</span>
        </div>
        <button 
          onClick={fetchTrades}
          disabled={loading}
          className="text-[10px] text-[var(--color-text-dim)] hover:text-[var(--color-accent)] transition-colors flex items-center gap-1 uppercase tracking-wider font-medium"
        >
          <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
          {loading ? 'Refreshing...' : 'Refresh History'}
        </button>
      </div>

      <div className="panel overflow-hidden">
        {/* Search bar */}
        <div className="px-4 py-3 border-b border-[var(--color-border-subtle)] flex justify-between items-center">
          <div className="flex items-center gap-2 border border-[var(--color-border-light)] rounded-lg px-3 py-2 w-64 bg-[var(--color-bg-input)]">
            <Search size={13} className="text-[var(--color-text-dim)] flex-shrink-0" />
            <input
              id="trade-search"
              type="text"
              placeholder="Search trades..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-transparent border-none outline-none text-xs w-full text-[var(--color-text-primary)] placeholder-[var(--color-text-dim)] font-medium"
            />
          </div>
          <span className="text-[10px] text-[var(--color-text-dim)] font-mono">
            {filtered.length} trades found
          </span>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Symbol</th>
                <th>Strategy</th>
                <th className="text-right">P&L ($)</th>
                <th className="text-right">Balance ($)</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-[var(--color-text-dim)] italic !font-sans">
                    {loading ? 'Fetching history...' : 'No real trades found in MT5 history for the last 30 days.'}
                  </td>
                </tr>
              ) : (
                filtered.map((row, i) => (
                  <tr key={i}>
                    <td className="!text-[var(--color-text-dim)] font-mono text-[11px]">
                      {new Date(row.time).toLocaleString('en-GB', { hour12: false })}
                    </td>
                    <td className="font-bold text-[var(--color-accent)]">{row.symbol}</td>
                    <td>
                      <span className="badge badge-outline text-[10px] opacity-70 uppercase">
                        {row.strategy}
                      </span>
                    </td>
                    <td className={`text-right font-bold ${row.pnl >= 0 ? '!text-[var(--color-success)]' : '!text-[var(--color-danger)]'}`}>
                      {row.pnl >= 0 ? '+' : ''}{row.pnl.toFixed(2)}
                    </td>
                    <td className="text-right font-mono text-[var(--color-text-muted)]">
                      {row.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
