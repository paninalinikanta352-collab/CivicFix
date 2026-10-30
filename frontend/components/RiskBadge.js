export default function RiskBadge({ risk }) {
  if (risk === null || risk === undefined) {
    return <div className="risk">Risk: --</div>;
  }
  const pct = Number(risk);
  const level = pct >= 70 ? "high" : pct >= 40 ? "med" : "low";
  return <div className={`risk ${level}`}>Risk: {pct}%</div>;
}