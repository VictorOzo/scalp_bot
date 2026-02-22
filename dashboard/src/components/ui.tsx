'use client';

import Link from 'next/link';
import { HTMLAttributes, ReactNode } from 'react';

export function Card({ children, ...rest }: { children: ReactNode } & HTMLAttributes<HTMLDivElement>) {
  return <div className="rounded-lg border border-slate-800 bg-slate-900 p-4" {...rest}>{children}</div>;
}

export function Badge({ text, variant }: { text: string; variant: 'green' | 'yellow' | 'red' | 'slate' }) {
  const cls = {
    green: 'bg-emerald-900 text-emerald-300',
    yellow: 'bg-amber-900 text-amber-300',
    red: 'bg-rose-900 text-rose-300',
    slate: 'bg-slate-700 text-slate-200'
  }[variant];
  return <span className={`rounded px-2 py-1 text-xs ${cls}`}>{text}</span>;
}

export function SidebarLink({ href, label }: { href: string; label: string }) {
  return <Link className="block rounded px-3 py-2 hover:bg-slate-800" href={href}>{label}</Link>;
}
