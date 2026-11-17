import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setUnauthorizedHandler, tokenStore } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!tokenStore.get()) { setLoading(false); return }
    api.get('/auth/me').then((r) => setUser(r.data)).catch(() => tokenStore.clear()).finally(() => setLoading(false))
  }, [logout])

  const startSession = (data) => {
    tokenStore.set(data.access_token)
    setUser(data.user)
  }

  const value = useMemo(() => ({
    user,
    loading,
    setUser,
    logout,
    /** Replace the session token (after a password change the server issues a new one). */
    setToken: (t) => tokenStore.set(t),
    refreshUser: async () => { if (tokenStore.get()) setUser((await api.get('/auth/me')).data) },
    login: async (email, password) => startSession((await api.post('/auth/login', { email, password })).data),
    register: async (payload) => startSession((await api.post('/auth/register', payload)).data),
  }), [user, loading, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
