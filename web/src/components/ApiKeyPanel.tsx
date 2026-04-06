import { useState } from 'react'
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '../lib/api'
import ApiDisconnected from './ApiDisconnected'

export default function ApiKeyPanel() {
  const { data, isPending, isError, refetch } = useApiKeys()
  const create = useCreateApiKey()
  const revoke = useRevokeApiKey()
  const [name, setName] = useState('')
  const [role, setRole] = useState('agent')
  const [createdKey, setCreatedKey] = useState<string | null>(null)

  const handleCreate = () => {
    if (!name.trim()) return
    create.mutate(
      { name: name.trim(), role },
      {
        onSuccess: (d) => {
          setCreatedKey(d.raw_key ?? null)
          setName('')
        },
      },
    )
  }

  return (
    <section>
      <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">API Keys & RBAC</h2>

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">Key Name</label>
          <input
            className="glass-input rounded-lg px-3 py-2 text-sm text-zinc-100"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-agent"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">Role</label>
          <select
            className="glass-input rounded-lg px-3 py-2 text-sm text-zinc-100"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="admin">Admin</option>
            <option value="agent">Agent</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
        <button
          onClick={handleCreate}
          disabled={create.isPending || !name.trim()}
          className="rounded-lg bg-gradient-to-r from-blue-600 to-blue-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/10 transition-all hover:shadow-blue-500/20 hover:brightness-110 disabled:opacity-50"
        >
          Create Key
        </button>
      </div>

      {createdKey && (
        <div className="mb-4 rounded-xl border border-emerald-500/20 bg-emerald-950/15 p-4">
          <p className="text-xs text-emerald-400">
            New key created — copy it now, it won't be shown again:
          </p>
          <code className="mt-1.5 block break-all font-mono text-sm text-emerald-300">
            {createdKey}
          </code>
        </div>
      )}

      {isError ? (
        <ApiDisconnected refetch={() => refetch()} compact />
      ) : isPending ? (
        <p className="text-sm text-zinc-600">Loading…</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-800/30 bg-zinc-900/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800/30 text-[11px] uppercase tracking-widest text-zinc-600">
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Prefix</th>
                <th className="px-4 py-3 text-left">Role</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {(data?.keys ?? []).map((k) => (
                <tr key={k.id} className="border-b border-zinc-800/15 transition-colors hover:bg-zinc-800/20">
                  <td className="px-4 py-2.5 text-zinc-200">{k.name}</td>
                  <td className="px-4 py-2.5 font-mono text-zinc-500">{k.key_prefix}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                        k.role === 'admin'
                          ? 'bg-violet-500/15 text-violet-400'
                          : k.role === 'agent'
                            ? 'bg-blue-500/15 text-blue-400'
                            : 'bg-zinc-500/15 text-zinc-500'
                      }`}
                    >
                      {k.role}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    {k.is_active ? (
                      <span className="flex items-center gap-1.5 text-xs">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                        <span className="text-emerald-400">active</span>
                      </span>
                    ) : (
                      <span className="text-xs text-zinc-600">revoked</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {k.is_active && (
                      <button
                        onClick={() => revoke.mutate(k.id)}
                        className="rounded-md px-2 py-1 text-[11px] text-zinc-600 transition-colors hover:bg-rose-500/10 hover:text-rose-400"
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 rounded-xl border border-zinc-800/20 bg-zinc-900/20 p-4">
        <p className="text-xs text-zinc-500">
          <span className="text-violet-400">admin</span> — full access &nbsp;|&nbsp;
          <span className="text-blue-400">agent</span> — read + trade &nbsp;|&nbsp;
          <span className="text-zinc-400">viewer</span> — read only
        </p>
        <p className="mt-1 text-[11px] text-zinc-600">
          Authenticate with <code className="rounded bg-zinc-800/50 px-1.5 py-0.5 text-zinc-400">X-API-Key</code> header.
          Set <code className="rounded bg-zinc-800/50 px-1.5 py-0.5 text-zinc-400">REQUIRE_AUTH=1</code> to enforce.
        </p>
      </div>
    </section>
  )
}
