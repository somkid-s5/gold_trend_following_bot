import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { ResponsiveContainer, LineChart, Line } from 'recharts';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { API } from '../config';

interface GuardData {
  status?: string;
  metrics?: {
    total_trades?: number;
    win_rate_window?: number;
    net_profit_window?: number;
    max_drawdown_pct_window?: number;
    max_consecutive_losses?: number;
  };
}

const generateSparkline = (trend: 'up' | 'down' | 'flat' = 'up') => {
  let v = 50;
  return Array.from({ length: 12 }, () => {
    const bias = trend === 'up' ? 2 : trend === 'down' ? -2 : 0;
    v += bias + (Math.random() - 0.5) * 8;
    v = Math.max(10, Math.min(90, v));
    return { v };
  });
};

function MetricCard({
  title, value, sub, trend, sparkline, sparkColor, delay = 0
}: {
  title: string; value: string; sub: string;
  trend?: 'up' | 'down' | 'neutral';
  sparkline?: { v: number }[];
  sparkColor?: string;
  delay?: number;
}) {
  const trendColors = {
    up: 'text-[var(--color-success)]',
    down: 'text-[var(--color-danger)]',
    neutral: 'text-[var(--color-text-muted)]',
  };
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;

  return (
    <div className="panel p-4 flex flex-col justify-between min-h-[110px]"
      style={{ animationDelay: `${delay}ms` }}>
      <div>
        <div className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-[0.1em] mb-1.5">
          {title}
        </div>
        <div className="text-xl font-bold text-[var(--color-text-primary)] text-number leading-none">
          {value}
        </div>
      </div>
      <div className="flex justify-between items-end mt-2">
        <div className={`text-[10px] font-semibold flex items-center gap-1 ${trend ? trendColors[trend] : 'text-[var(--color-text-dim)]'}`}>
          {trend && <TrendIcon size={10} />}
          {sub}
        </div>
        {sparkline && (
          <div className="w-14 h-6 opacity-70" style={{ minWidth: 56, minHeight: 24 }}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
              <LineChart data={sparkline}>
                <Line
                  type="monotone"
                  dataKey="v"
                  stroke={sparkColor || 'var(--color-primary)'}
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

interface Props {
  apiOnline: boolean;
}

export default function MetricsSection({ apiOnline }: Props) {
  const [guard, setGuard] = useState<GuardData>({});

  const fetchGuard = useCallback(async () => {
    if (!apiOnline) return;
    try {
      const res = await axios.get(API.MONITOR.STATUS, { timeout: 3000 });
      if (res.data.guard) setGuard(res.data.guard);
    } catch {
      // silent
    }
  }, [apiOnline]);

  useEffect(() => {
    fetchGuard();
    const interval = setInterval(fetchGuard, 15000);
    return () => clearInterval(interval);
  }, [fetchGuard]);

  const winRate = guard.metrics?.win_rate_window ?? 0;
  const totalTrades = guard.metrics?.total_trades ?? 0;
  const netPnl = guard.metrics?.net_profit_window ?? 0;
  const maxDd = guard.metrics?.max_drawdown_pct_window ?? 0;
  const maxConsLosses = guard.metrics?.max_consecutive_losses ?? 0;

  return (
    <section className="animate-fadeInUp" style={{ animationDelay: '100ms' }}>
      <div className="section-header justify-between">
        <div className="flex items-center gap-2">
          <span className="section-number">02</span>
          <span className="uppercase tracking-wider">Metrics & Risk</span>
        </div>
        <span className="text-[10px] text-[var(--color-text-dim)] uppercase tracking-wider hidden sm:block font-medium">
          Live from MT5 History
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 stagger">
        <MetricCard
          title="Total Trades"
          value={totalTrades.toLocaleString()}
          sub={totalTrades > 0 ? "Last 30 days" : "No trades found"}
          trend={totalTrades > 0 ? 'neutral' : undefined}
          sparkline={generateSparkline('up')}
        />
        <MetricCard
          title="Win Rate"
          value={totalTrades > 0 ? `${winRate.toFixed(1)}%` : '---'}
          sub={winRate >= 50 ? 'Healthy' : 'Sub-optimal'}
          trend={winRate >= 50 ? 'up' : 'down'}
          delay={60}
        />
        <MetricCard
          title="Net P&L"
          value={`$${Math.abs(netPnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          sub={netPnl >= 0 ? 'Profit' : 'Loss'}
          trend={netPnl >= 0 ? 'up' : 'down'}
          sparkline={generateSparkline(netPnl >= 0 ? 'up' : 'down')}
          sparkColor={netPnl >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}
          delay={120}
        />
        <MetricCard
          title="Max Drawdown"
          value={`${maxDd.toFixed(2)}%`}
          sub="Recent period"
          trend="down"
          delay={180}
        />
        <MetricCard
          title="Max Streak"
          value={`${maxConsLosses}`}
          sub="Loss streak"
          trend={maxConsLosses < 5 ? 'up' : 'down'}
          sparkline={generateSparkline(maxConsLosses < 5 ? 'up' : 'flat')}
          delay={240}
        />
      </div>

      {/* Risk Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        <div className="panel p-5">
          <div className="flex justify-between items-center mb-3">
            <span className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-[0.1em]">
              Recent Drawdown vs Limit
            </span>
            <span className="text-lg font-bold text-number text-[var(--color-text-primary)]">
              {maxDd.toFixed(1)}%
            </span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${Math.min((maxDd / 5) * 100, 100)}%`,
                background: maxDd > 4.0
                  ? 'linear-gradient(90deg, var(--color-danger), #ef4444)'
                  : maxDd > 2.5
                    ? 'linear-gradient(90deg, var(--color-warning), var(--color-primary))'
                    : 'linear-gradient(90deg, var(--color-success), #34d399)',
              }}
            />
          </div>
          <div className="flex justify-between mt-2.5 text-[10px] text-[var(--color-text-dim)] font-medium">
            <span>Current: {maxDd.toFixed(2)}%</span>
            <span>Soft Limit: 5.0%</span>
          </div>
        </div>

        <div className="panel p-5">
          <div className="flex justify-between items-center mb-3">
            <span className="text-[10px] font-bold text-[var(--color-text-dim)] uppercase tracking-[0.1em]">
              Win Rate Performance
            </span>
            <span className="text-lg font-bold text-number text-[var(--color-text-primary)]">
              {winRate.toFixed(1)}%
            </span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${Math.min(winRate, 100)}%`,
                background: winRate >= 50
                  ? 'linear-gradient(90deg, var(--color-primary), #f59e0b)'
                  : 'linear-gradient(90deg, var(--color-danger), #ef4444)',
              }}
            />
          </div>
          <div className="flex justify-between mt-2.5 text-[10px] text-[var(--color-text-dim)] font-medium">
            <span>Win Rate</span>
            <span>Target: 50%+</span>
          </div>
        </div>
      </div>
    </section>
  );
}
