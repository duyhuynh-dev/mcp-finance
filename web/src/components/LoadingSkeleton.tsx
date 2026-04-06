export default function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3 p-5">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4" style={{ animationDelay: `${i * 120}ms` }}>
          <div className="skeleton h-4 w-20" />
          <div className="skeleton h-4 flex-1" />
          <div className="skeleton h-4 w-16" />
        </div>
      ))}
    </div>
  )
}
