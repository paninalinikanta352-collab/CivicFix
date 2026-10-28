"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getUser, clearAuth } from "../lib/api";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/report", label: "Report" },
  { href: "/dashboard", label: "My Issues" },
];

export default function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState(null);

  useEffect(() => {
    setUser(getUser());
  }, [pathname]);

  const links =
    user?.role === "admin"
      ? [...LINKS, { href: "/admin", label: "Admin" }]
      : user?.role === "worker"
      ? [...LINKS, { href: "/worker", label: "My Duty" }]
      : LINKS;

  const logout = () => {
    clearAuth();
    setUser(null);
    router.push("/");
  };

  return (
    <header className="topbar">
      <Link href="/" className="logo">CivicFix</Link>
      <nav className="nav">
        {links.map((l) => (
          <Link key={l.href} href={l.href} className={pathname === l.href ? "active" : ""}>
            {l.label}
          </Link>
        ))}
      </nav>
      <div className="top-right">
        {user ? (
          <>
            <span className="badge" title={user.email}>{user.name} · {user.role}</span>
            <button className="btn small ghost" onClick={logout}>Logout</button>
          </>
        ) : (
          <>
            <Link href="/login" className="btn small">Login</Link>
            <Link href="/register" className="btn small primary">Sign up</Link>
          </>
        )}
      </div>
    </header>
  );
}
