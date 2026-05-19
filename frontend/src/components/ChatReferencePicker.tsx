type ChatReferencePickerProps = {
  urls: string[];
  selected: string[];
  saved: string[];
  maxSelect?: number;
  disabled?: boolean;
  onToggle: (url: string) => void;
};

export function ChatReferencePicker({
  urls,
  selected,
  saved,
  maxSelect = 2,
  disabled = false,
  onToggle,
}: ChatReferencePickerProps) {
  if (urls.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
        Reference options — tap to select (max {maxSelect})
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {urls.map((url, i) => {
          const isSelected = selected.includes(url);
          const isSaved = saved.includes(url);
          return (
            <button
              key={`${i}-${url.slice(0, 48)}`}
              type="button"
              disabled={disabled || (!isSelected && selected.length >= maxSelect)}
              onClick={() => onToggle(url)}
              className={`group relative overflow-hidden rounded-xl border-2 bg-white text-left transition ${
                isSelected
                  ? "border-accent ring-2 ring-accent/30"
                  : "border-zinc-200 hover:border-zinc-300 disabled:opacity-50"
              }`}
            >
              <img
                src={url}
                alt={`Reference option ${i + 1}`}
                className="aspect-[4/5] w-full object-cover"
              />
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-2">
                <span className="text-[10px] font-semibold text-white">Option {i + 1}</span>
              </div>
              {isSelected ? (
                <span className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-accent text-xs font-bold text-white shadow">
                  ✓
                </span>
              ) : null}
              {isSaved && !isSelected ? (
                <span className="absolute left-2 top-2 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold text-white shadow">
                  Saved
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
