type ChevronLeftIconProps = {
  className?: string;
};

export function ChevronLeftIcon({ className = "w-3.5 h-3.5" }: ChevronLeftIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M10 12L6 8l4-4" />
    </svg>
  );
}
