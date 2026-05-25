type ChevronDownIconProps = {
  className?: string;
};

export function ChevronDownIcon({
  className = "w-3.5 h-3.5 shrink-0",
}: ChevronDownIconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
  );
}
