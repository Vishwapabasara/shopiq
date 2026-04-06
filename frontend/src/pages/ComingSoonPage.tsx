import { EmptyState } from '../components/ui'

interface Props {
  module: string
  description: string
  icon: string
}

export function ComingSoonPage({ module, description, icon }: Props) {
  return (
    <div className="flex-1 flex flex-col">
      <div className="bg-white border-b border-slate-200 px-8 py-4">
        <h1 className="text-base font-semibold text-slate-900">{module}</h1>
        <p className="text-xs text-slate-400 mt-0.5">Coming soon</p>
      </div>
      <div className="flex-1 flex items-center justify-center">
        <EmptyState
          icon={icon}
          title={`${module} is coming soon`}
          description={description}
          action={
            <button className="btn-primary opacity-60 cursor-default">
              Join waitlist
            </button>
          }
        />
      </div>
    </div>
  )
}
