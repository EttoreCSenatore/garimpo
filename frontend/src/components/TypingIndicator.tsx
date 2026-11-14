/** Three animated dots shown while the bot is fetching */
export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      {/* Bot avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600
                      flex items-center justify-center shadow-sm">
        <span className="text-white text-xs font-bold">AI</span>
      </div>

      <div className="bg-white border border-slate-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <div className="flex gap-1.5 items-center h-4">
          <span className="typing-dot w-2 h-2 rounded-full bg-slate-400 block" />
          <span className="typing-dot w-2 h-2 rounded-full bg-slate-400 block" />
          <span className="typing-dot w-2 h-2 rounded-full bg-slate-400 block" />
        </div>
      </div>
    </div>
  )
}
