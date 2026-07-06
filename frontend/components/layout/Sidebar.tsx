"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard,
  Mic,
  PlusCircle,
  GraduationCap,
  Search,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "dashboard", icon: LayoutDashboard },
  { href: "/dashboard/sessions", label: "sessions", icon: Mic },
  { href: "/dashboard/sessions/new", label: "newSession", icon: PlusCircle },
  { href: "/dashboard/coaching", label: "coaching", icon: GraduationCap },
  { href: "/dashboard/search", label: "search", icon: Search },
  { href: "/dashboard/settings", label: "settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  return (
    <aside className="flex h-full w-64 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex h-14 items-center border-b border-zinc-200 px-6 dark:border-zinc-800">
        <Link href="/dashboard" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Acoustic Comms
        </Link>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-teal-100 text-teal-900 dark:bg-teal-900/30 dark:text-teal-100"
                  : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800",
              )}
            >
              <Icon className="h-4 w-4" />
              {t(label)}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
