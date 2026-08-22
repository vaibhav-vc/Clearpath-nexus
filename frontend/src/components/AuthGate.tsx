import { useEffect, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { LOCAL_DEMO_MODE, supabase, onAuthStateChange } from '../services/supabaseClient'

/**
 * Wraps the dashboard and blocks it behind a Supabase session.
 *
 * Before this, App.tsx rendered CommandDashboard directly with no session at
 * all, so every backend call went out with no Authorization header and the
 * backend (which requires a valid Supabase JWT on /planner and /port routes)
 * rejected it with 401. This is the minimum needed to get a real token into
 * the app; it intentionally does not attempt sign-up, password reset, etc.
 */
export default function AuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [checking, setChecking] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (LOCAL_DEMO_MODE) {
      setChecking(false)
      return
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setChecking(false)
    })
    return onAuthStateChange(setSession)
  }, [])

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError(error.message)
    setSubmitting(false)
  }

  if (checking) {
    return <div className="flex h-screen items-center justify-center text-slate-400">Loading…</div>
  }

  if (LOCAL_DEMO_MODE) {
    return <>{children}</>
  }

  if (!session) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <form
          onSubmit={handleSignIn}
          className="w-80 space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-6"
        >
          <h1 className="text-lg font-semibold text-slate-100">ClearPath Nexus</h1>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-slate-100"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-slate-100"
            required
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-sky-600 px-3 py-2 font-medium text-white disabled:opacity-50"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    )
  }

  return <>{children}</>
}
