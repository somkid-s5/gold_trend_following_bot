import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { X, Save, AlertTriangle, CheckCircle } from 'lucide-react';
import { API } from '../config';

interface Props {
  onClose: () => void;
}

type SaveState = 'idle' | 'saving' | 'success' | 'error';

export default function SettingsModal({ onClose }: Props) {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>('idle');

  const fetchConfig = useCallback(async () => {
    try {
      const res = await axios.get(API.CONFIG.GET, { timeout: 5000 });
      setConfig(res.data);
    } catch (e) {
      console.error('Failed to fetch config:', e);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const init = async () => {
      await fetchConfig();
    };
    init();
    
    // Close on Escape
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose, fetchConfig]);

  const handleSave = async () => {
    setSaveState('saving');
    try {
      await axios.put(API.CONFIG.UPDATE, config);
      setSaveState('success');
      setTimeout(() => onClose(), 1200);
    } catch (e) {
      console.error('Failed to save config:', e);
      setSaveState('error');
      setTimeout(() => setSaveState('idle'), 3000);
    }
  };

  const updateField = (path: string[], value: string | number) => {
    setConfig((prev: Record<string, unknown> | null) => {
      if (!prev) return null;
      const updated = JSON.parse(JSON.stringify(prev));
      let obj = updated as Record<string, unknown>;
      for (let i = 0; i < path.length - 1; i++) {
        obj = obj[path[i]] as Record<string, unknown>;
      }
      obj[path[path.length - 1]] = value;
      return updated;
    });
    setSaveState('idle');
  };


  return (
    <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-[var(--color-border-subtle)] flex justify-between items-center flex-shrink-0">
          <div>
            <h2 className="text-base font-bold text-[var(--color-text-primary)]">Bot Configuration</h2>
            <p className="text-[10px] text-[var(--color-text-dim)] mt-0.5 uppercase tracking-wider">
              config/config.yaml
            </p>
          </div>
          <button
            id="btn-close-settings"
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-white/5 transition-all"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {loading ? (
            <div className="text-sm text-[var(--color-text-muted)] text-center py-16 font-medium">
              Loading configuration...
            </div>
          ) : !config ? (
            <div className="text-sm text-[var(--color-danger)] text-center py-16 flex flex-col items-center gap-2">
              <AlertTriangle size={24} />
              Failed to load config. Make sure the API is running.
            </div>
          ) : (
            <>
              {/* Risk Management */}
              <div>
                <h3 className="text-xs font-bold text-[var(--color-primary)] uppercase tracking-wider mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)]"></span>
                  Risk Management
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <InputRow label="Risk Per Trade (%)" path={['risk', 'risk_per_trade_pct']} config={config} updateField={updateField} step="0.1" />
                  <InputRow label="Max Daily Loss (%)" path={['risk', 'max_daily_loss_pct']} config={config} updateField={updateField} step="0.1" />
                  <InputRow label="Max Drawdown (%)" path={['risk', 'max_total_drawdown_pct']} config={config} updateField={updateField} step="0.1" />
                  <InputRow label="Max Spread (pts)" path={['risk', 'max_spread_points']} config={config} updateField={updateField} step="10" />
                  <InputRow label="Scaling Delta ($)" path={['risk', 'scaling_delta']} config={config} updateField={updateField} step="10" />
                  <InputRow label="Breakeven RR Trigger" path={['risk', 'breakeven_rr_trigger']} config={config} updateField={updateField} step="0.1" />
                </div>
              </div>

              {/* Strategy */}
              <div className="pt-4 border-t border-[var(--color-border-subtle)]">
                <h3 className="text-xs font-bold text-[var(--color-accent)] uppercase tracking-wider mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]"></span>
                  Trend Following
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <InputRow label="Fast EMA" path={['strategies', 'trend_following', 'fast_ema']} config={config} updateField={updateField} />
                  <InputRow label="Slow EMA" path={['strategies', 'trend_following', 'slow_ema']} config={config} updateField={updateField} />
                  <InputRow label="RSI Period" path={['strategies', 'trend_following', 'rsi_period']} config={config} updateField={updateField} />
                  <InputRow label="ATR Period" path={['strategies', 'trend_following', 'atr_period']} config={config} updateField={updateField} />
                  <InputRow label="ATR SL Multiplier" path={['strategies', 'trend_following', 'atr_sl_multiplier']} config={config} updateField={updateField} step="0.1" />
                  <InputRow label="Take Profit RR" path={['strategies', 'trend_following', 'take_profit_rr']} config={config} updateField={updateField} step="0.1" />
                </div>
              </div>

              {/* Trading */}
              <div className="pt-4 border-t border-[var(--color-border-subtle)]">
                <h3 className="text-xs font-bold text-[var(--color-success)] uppercase tracking-wider mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)]"></span>
                  Trading
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <InputRow label="Symbol" path={['trading', 'symbol']} config={config} updateField={updateField} type="text" />
                  <InputRow label="Poll Interval (sec)" path={['trading', 'poll_seconds']} config={config} updateField={updateField} />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--color-border-subtle)] flex justify-between items-center flex-shrink-0">
          <button
            onClick={onClose}
            className="btn-primary btn-ghost text-xs py-2 px-4"
          >
            Cancel
          </button>

          <button
            id="btn-save-config"
            onClick={handleSave}
            disabled={saveState === 'saving' || loading || !config}
            className={`btn-primary text-xs py-2 px-5 ${
              saveState === 'success' ? 'btn-engage' :
              saveState === 'error' ? 'btn-stop' : 'btn-engage'
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {saveState === 'saving' ? (
              <>Saving...</>
            ) : saveState === 'success' ? (
              <><CheckCircle size={14} /> Saved!</>
            ) : saveState === 'error' ? (
              <><AlertTriangle size={14} /> Failed</>
            ) : (
              <><Save size={14} /> Save Configuration</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

const InputRow = ({ label, path, config, updateField, type = 'number', step }: { label: string; path: string[]; config: Record<string, unknown> | null; updateField: (path: string[], v: string | number) => void; type?: string; step?: string }) => {
  let value: unknown = config;
  if (value && typeof value === 'object') {
    for (const key of path) {
      value = (value as Record<string, unknown>)?.[key];
    }
  }

  return (
    <div>
      <label className="block text-[11px] font-semibold text-[var(--color-text-dim)] uppercase tracking-wider mb-1.5">
        {label}
      </label>
      <input
        type={type}
        step={step}
        value={(value as string | number | undefined) ?? ''}
        onChange={(e) => {
          const v = type === 'number' ? parseFloat(e.target.value) : e.target.value;
          updateField(path, v);
        }}
        className="input-field text-number"
      />
    </div>
  );
};
