import type { ThemeMode } from "../types";

interface ThemeToggleIconProps {
  theme: ThemeMode;
}

export function ThemeToggleIcon({ theme }: ThemeToggleIconProps) {
  if (theme === "dark") {
    return (
      <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
        <circle cx="8" cy="8" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path
          d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.3 3.3l1.3 1.3M11.4 11.4l1.3 1.3M12.7 3.3l-1.3 1.3M4.6 11.4l-1.3 1.3"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.3"
        />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
      <path
        d="M10.9 1.8a5.8 5.8 0 1 0 3.3 10.3A6.3 6.3 0 0 1 10.9 1.8Z"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.4"
      />
    </svg>
  );
}
