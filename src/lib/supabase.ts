// src/lib/supabase.ts
import { createClient } from '@supabase/supabase-js'

// With the auth gate off (VITE_AUTH_ENABLED=false) there may be no Supabase
// project configured at all. createClient throws on an empty URL, which would
// take down the whole app at import time — so fall back to a harmless
// placeholder. Nothing calls the network in that mode; getSession() only reads
// localStorage.
const supabaseUrl =
  (import.meta.env.VITE_SUPABASE_URL as string) || 'http://localhost:54321'
const supabaseAnonKey =
  (import.meta.env.VITE_SUPABASE_ANON_KEY as string) || 'local-anon-key'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
