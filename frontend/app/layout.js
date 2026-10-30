import Topbar from "../components/Topbar";
import "./globals.css";

export const metadata = {
  title: "CivicFix - Spot it. Snap it. Fix it.",
  description: "Report civic problems. Get them fixed.",
};

const THEME_INIT = `try{var t=localStorage.getItem("civicfix_theme");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t}}catch(e){}`;

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
        <Topbar />
        {children}
        <footer>CivicFix — spot it, snap it, fix it. Every report makes the neighborhood safer.</footer>
      </body>
    </html>
  );
}
