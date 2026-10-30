import Topbar from "../components/Topbar";
import "./globals.css";

export const metadata = {
  title: "CivicFix - Spot it. Snap it. Fix it.",
  description: "Report civic problems. Get them fixed.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Topbar />
        {children}
        <footer>CivicFix — spot it, snap it, fix it. Every report makes the neighborhood safer.</footer>
      </body>
    </html>
  );
}
