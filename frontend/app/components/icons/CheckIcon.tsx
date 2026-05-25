type CheckIconProps = {
  className?: string;
};

export function CheckIcon({ className = "w-3.5 h-3.5 shrink-0" }: CheckIconProps) {
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
      <path d="M3.5 8l3 3 6-6" />
    </svg>
  );
}
