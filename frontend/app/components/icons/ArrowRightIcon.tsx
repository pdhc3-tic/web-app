type ArrowRightIconProps = {
  className?: string;
};

export function ArrowRightIcon({
  className = "w-3.5 h-3.5",
}: ArrowRightIconProps) {
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
      <path d="M3 8h10M9 4l4 4-4 4" />
    </svg>
  );
}
