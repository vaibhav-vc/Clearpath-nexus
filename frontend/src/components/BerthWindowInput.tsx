interface Props {
  enabled: boolean
  start: string
  end: string
  onEnabledChange: (value: boolean) => void
  onStartChange: (value: string) => void
  onEndChange: (value: string) => void
}

export default function BerthWindowInput({
  enabled,
  start,
  end,
  onEnabledChange,
  onStartChange,
  onEndChange,
}: Props) {
  return (
    <div className="rounded-lg border border-indigo-500/30 bg-indigo-950/20 p-3 space-y-2">
      <label className="flex items-center gap-2 text-xs font-mono text-indigo-200">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onEnabledChange(e.target.checked)}
          className="accent-indigo-500"
        />
        Use operator berth window
      </label>
      {enabled ? (
        <div className="grid grid-cols-1 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-mono uppercase text-slate-400">Loading start</span>
            <input
              type="datetime-local"
              value={start}
              onChange={(e) => onStartChange(e.target.value)}
              className="rounded border border-slate-700 bg-slate-900/80 px-2 py-2 text-xs font-mono text-white"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-mono uppercase text-slate-400">Loading end</span>
            <input
              type="datetime-local"
              value={end}
              onChange={(e) => onEndChange(e.target.value)}
              className="rounded border border-slate-700 bg-slate-900/80 px-2 py-2 text-xs font-mono text-white"
            />
          </label>
          <p className="text-[10px] font-mono text-slate-500">
            Uses the operator/manifest window already supported by the backend; no fake live berth feed.
          </p>
        </div>
      ) : null}
    </div>
  )
}
