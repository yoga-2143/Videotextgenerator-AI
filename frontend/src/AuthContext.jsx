/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function verifySession() {
      const token = localStorage.getItem('vetri_token')
      if (!token) {
        setUser(null)
        setLoading(false)
        return
      }

      try {
        const data = await api.getMe()
        if (data?.user) {
          setUser(data.user)
          localStorage.setItem('vetri_user', JSON.stringify(data.user))
        } else {
          throw new Error('Invalid user payload')
        }
      } catch (err) {
        localStorage.removeItem('vetri_token')
        localStorage.removeItem('vetri_user')
        setUser(null)
      } finally {
        setLoading(false)
      }
    }

    verifySession()
  }, [])

  const signUp = useCallback(async (name, email, password, confirmPassword) => {
    const data = await api.signUp(name, email, password, confirmPassword)
    localStorage.setItem('vetri_token', data.token)
    localStorage.setItem('vetri_user', JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }, [])

  const signInWithEmail = useCallback(async (email, password) => {
    const data = await api.emailLogin(email, password)
    localStorage.setItem('vetri_token', data.token)
    localStorage.setItem('vetri_user', JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }, [])

  const signIn = useCallback(async (credential) => {
    const data = await api.googleLogin(credential)
    localStorage.setItem('vetri_token', data.token)
    localStorage.setItem('vetri_user', JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      // Backend logout endpoint response handled safely
    } finally {
      localStorage.removeItem('vetri_token')
      localStorage.removeItem('vetri_user')
      setUser(null)
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, signUp, signInWithEmail, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
