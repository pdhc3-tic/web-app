export function BrandMark() {
  return (
    <div className="flex items-center gap-2 text-primary">
      <svg
        viewBox="0 0 24 24"
        className="h-6 w-6"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 3 L20 19 L4 19 Z"
        />
      </svg>
      <span className="text-base font-semibold tracking-tight">
        PDHC <span className="font-light italic lowercase opacity-80">iii</span>
      </span>
    </div>
  );
}
