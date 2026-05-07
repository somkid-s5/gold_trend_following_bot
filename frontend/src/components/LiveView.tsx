import OverviewSection from './OverviewSection';
import MetricsSection from './MetricsSection';
import LogSection from './LogSection';
import HistorySection from './HistorySection';

interface Props {
  apiOnline: boolean;
  botRunning: boolean;
}

export default function LiveView({ apiOnline, botRunning }: Props) {
  return (
    <div className="space-y-8 animate-fadeIn">
      <OverviewSection apiOnline={apiOnline} />
      <MetricsSection apiOnline={apiOnline} />
      <LogSection apiOnline={apiOnline} botRunning={botRunning} />
      <HistorySection />
    </div>
  );
}
