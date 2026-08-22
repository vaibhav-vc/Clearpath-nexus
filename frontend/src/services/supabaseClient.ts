import { createClient, type Session } from '@supabase/supabase-js'

// Auth stays with Supabase, same as the Android client: we sign in here and
// lift the access token off the session to present to the backend as a
// bearer token. The backend verifies it via JWKS (see
// backend/app/core/security.py). No credentials are stored or minted here.
//
// The anon key is a public, RLS-scoped key (same one embedded in
// android/.../SupabaseClient.kt) - it is meant to ship in client bundles.
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined
export const LOCAL_DEMO_MODE = import.meta.env.VITE_LOCAL_DEMO_MODE === 'true'

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  // Fail loud in dev rather than silently sending unauthenticated requests
  // that the backend will 401 on one-by-one.
  console.error(
    '[supabaseClient] VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set. ' +
      'Auth will not work until these are configured in frontend/.env — see .env.example.',
  )
}

export const supabase = createClient(SUPABASE_URL ?? '', SUPABASE_ANON_KEY ?? '')

export async function getAccessToken(): Promise<string | null> {
  // The local MVP demo deliberately runs against a development backend with
  // AUTH_DISABLED=true. Do not contact a placeholder Supabase endpoint in
  // that explicit mode; production builds still require a real session.
  if (LOCAL_DEMO_MODE) return null
  const { data, error } = await supabase.auth.getSession()
  if (error) {
    console.warn('[supabaseClient] failed to read session', error)
    return null
  }
  return data.session?.access_token ?? null
}

export function onAuthStateChange(callback: (session: Session | null) => void) {
  const {
    data: { subscription },
  } = supabase.auth.onAuthStateChange((_event, session) => callback(session))
  return () => subscription.unsubscribe()
}
