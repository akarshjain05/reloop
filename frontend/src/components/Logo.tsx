export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#0E5257" />
      <path d="M22.5 11.2A8 8 0 1 0 24 16" fill="none" stroke="#F7F9F9" strokeWidth="3" strokeLinecap="round" />
      <circle cx="23.2" cy="9.4" r="2.6" fill="#F5B83D" />
    </svg>
  );
}
export const Logo = ({ light }: { light?: boolean }) => (
  <span className={`inline-flex items-center gap-2 font-display text-xl font-bold tracking-tight ${light ? "text-white" : "text-ink"}`}>
    <LogoMark />ReLoop
  </span>
);
