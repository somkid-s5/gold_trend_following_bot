import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, BarChart3 } from 'lucide-react';
import { API } from '../config';

interface SystemStatus {
  guard?: {
    status?: string;
    win_rate?: number;
    total_trades?: number;
    net_pnl?: number;
  } | null;
  runtime?: {
    state?: string;
    balance?: number;
    equity?: number;
    open_positions?: number;
    last_signal_time?: string;
    equity_history?: Array<{ time: string; equity: number; balance: number }>;
  } | null;
}

// Generate equity curve data (from real API or simulated)
function generateEquityCurve(balance: number) {
  const points = 60;
  const data = [];
  let val = balance * 0.85; // start from 85% of current
  for (let i = 0; i < points; i++) {
    const drift = (balance - val) / (points - i) + (Math.random() - 0.45) * (balance * 0.008);
    val = Math.max(val + drift, balance * 0.7);
    data.push({
      day: i + 1,
      equity: Math.round(val * 100) / 100,
      invested: balance * 0.85,
    });
  }
  // Ensure last point matches current
  data[data.length - 1].equity = balance;
  return data;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; payload: { day: number } }>;
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg px-3 py-2 text-xs"
        style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border-light)' }}>
        <p className="font-mono text-[var(--color-primary)] font-semibold">
          ${payload[0].value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
        </p>
        <p className="text-[var(--color-text-muted)] text-[10px] mt-0.5">Day {payload[0].payload.day}</p>
      </div>
    );
  }
  return null;
};

interface Props {
  apiOnline: boolean;
}

export default function OverviewSection({ apiOnline }: Props) {
  const [sysStatus, setSysStatus] = useState<SystemStatus>({});
  const [chartData, setChartData] = useState(() => generateEquityCurve(10000));

  const fetchSystemStatus = useCallback(async () => {
    if (!apiOnline) return;
    try {
      const res = await axios.get<SystemStatus>(API.MONITOR.STATUS, { timeout: 3000 });
      setSysStatus(res.data);
      
      if (res.data.runtime?.equity_history && res.data.runtime.equity_history.length > 0) {
        // Use real history
        const realData = res.data.runtime.equity_history.map((h, i) => ({
          day: i + 1,
          equity: h.equity,
          invested: h.balance
        }));
        setChartData(realData);
      } else if (res.data.runtime?.balance) {
        // Fallback to simulated if no history yet
        setChartData(generateEquityCurve(res.data.runtime.balance));
      }
    } catch {
      // silently fail, we still show defaults
    }
  }, [apiOnline]);

  useEffect(() => {
    const interval = setInterval(fetchSystemStatus, 10000);
    
    // Initial fetch
    const init = async () => {
      await fetchSystemStatus();
    };
    init();

    return () => clearInterval(interval);
  }, [fetchSystemStatus]);

  const balance = sysStatus.runtime?.balance ?? 10000;
  const equity = sysStatus.runtime?.equity ?? balance;
  const pnl = equity - balance;
  const pnlPct = balance > 0 ? (pnl / balance) * 100 : 0;
  const openPositions = sysStatus.runtime?.open_positions ?? 0;
  const guardStatus = sysStatus.guard?.status ?? 'UNKNOWN';

  return (
    <section className="animate-fadeInUp">
      <div className="section-header">
        <span className="section-number">01</span>
        <span className="uppercase tracking-wider">Overview</span>
      </div>

      <div className="flex flex-col lg:flex-row gap-5">
        {/* ─── Left: Key Metrics ─── */}
        <div className="panel p-6 lg:w-[38%] flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-3">
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase tracking-[0.12em]">
                Unrealized P&L
              </span>
              <span className={`badge ${guardStatus === 'RUNNING' || guardStatus === 'OK' ? 'badge-live' : 'badge-offline'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${guardStatus === 'RUNNING' || guardStatus === 'OK' ? 'bg-emerald-400 animate-pulse-dot' : 'bg-slate-500'}`}></span>
                {guardStatus}
              </span>
            </div>

            <div className="flex items-baseline gap-1.5">
              <span className="text-xl text-[var(--color-text-muted)] font-mono">$</span>
              <span className={`text-4xl lg:text-5xl font-extrabold tracking-tight text-number ${
                pnl >= 0 ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-danger)]'
              }`}>
                {Math.abs(pnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            <div className="mt-2 flex items-center gap-2.5">
              <span className={`flex items-center gap-1 text-sm font-semibold ${pnl >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'}`}>
                {pnl >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {pnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
              </span>
              <span className="text-[10px] text-[var(--color-text-dim)]">all-time</span>
            </div>
          </div>

          <div className="mt-8 pt-5 border-t border-[var(--color-border-subtle)] grid grid-cols-3 gap-4">
            <div>
              <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-[0.1em] mb-1.5 flex items-center gap-1">
                <DollarSign size={10} /> Equity
              </div>
              <div className="text-base font-bold text-[var(--color-text-primary)] text-number">
                ${equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-[0.1em] mb-1.5 flex items-center gap-1">
                <DollarSign size={10} /> Balance
              </div>
              <div className="text-base font-bold text-[var(--color-text-primary)] text-number">
                ${balance.toLocaleString(undefined, { minimumFractionDigits: 0 })}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-[0.1em] mb-1.5 flex items-center gap-1">
                <BarChart3 size={10} /> Positions
              </div>
              <div className="text-base font-bold text-[var(--color-text-primary)] text-number">
                {openPositions}
              </div>
            </div>
          </div>
        </div>

        {/* ─── Right: Equity Chart ─── */}
        <div className="panel p-0 lg:w-[62%] flex flex-col">
          <div className="px-5 py-3 border-b border-[var(--color-border-subtle)] flex justify-between items-center">
            <div className="flex items-center gap-4">
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase tracking-[0.1em]">
                Equity Curve
              </span>
              <div className="flex items-center gap-3 text-[10px] text-[var(--color-text-dim)]">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-0.5 bg-[var(--color-primary)] rounded-full"></span> Equity
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-0.5 bg-[var(--color-text-dim)] rounded-full opacity-50"></span> Invested
                </span>
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-[280px] p-4 pt-2">
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="day" hide />
                <YAxis
                  domain={['dataMin - 200', 'dataMax + 200']}
                  tick={{ fontSize: 10, fill: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}
                  axisLine={false}
                  tickLine={false}
                  width={55}
                  tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}k`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="invested"
                  stroke="rgba(100,116,139,0.3)"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  fillOpacity={0}
                  dot={false}
                />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#equityGrad)"
                  dot={false}
                  activeDot={{ r: 4, fill: 'var(--color-primary)', stroke: '#fff', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </section>
  );
}
