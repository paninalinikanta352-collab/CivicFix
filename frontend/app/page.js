import Link from "next/link";

const STEPS = [
  ["📸", "Snap a photo", "Take a clear photo of the problem you spotted."],
  ["📍", "Pin the location", "One tap adds your live GPS so crews know where to go."],
  ["🛠️", "We get it fixed", "The admin reviews the risk and sends the right worker."],
  ["✅", "Track progress", "Watch your report move from Assigned to Resolved."],
];

export default function Home() {
  return (
    <main className="wrap">
      <section className="hero">
        <h1>Spot it. Snap it. Fix it.</h1>
        <p>Report civic problems in your area — photo, live location, and progress tracking, all on file.</p>
        <div className="hero-row">
          <Link href="/report" className="btn primary">📸 Report a Problem</Link>
          <Link href="/register" className="btn">Create an Account</Link>
        </div>
      </section>

      <section className="how">
        {STEPS.map(([icon, title, text]) => (
          <div className="how-card" key={title}>
            <div className="how-icon">{icon}</div>
            <h3>{title}</h3>
            <p>{text}</p>
          </div>
        ))}
      </section>

      <section className="card">
        <h2>Why it works</h2>
        <p>Every report gets an AI-based risk score, so the most dangerous problems — open wires, deep potholes,
        leaks near schools and hospitals — move to the top of the queue first.</p>
      </section>
    </main>
  );
}
