'use client';

/**
 * Concept: Enterprise Authentication & Multi-Tenant Lifecycle Context
 * 
 * Manages JWT storage, active tenant extraction, 1-hour expiration countdown,
 * and automated 401 redirect handling.
 * 
 * Lifecycle Details:
 * 1. User signs in via POST /v1/auth/login.
 * 2. Token stored in localStorage under 'vigil_token'.
 * 3. Extracts TokenPayload (sub, tenant_id, role, exp). Role used strictly for UI hints.
 * 4. 1-Hour TTL: Tokens automatically expire at exp * 1000. On expiry or 401, session clears
 *    and redirects to /login?redirect=<intended_url>.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { TokenPayload, LoginResponse } from '../lib/types';
import { api, decodeTokenPayload } from '../lib/api';

interface AuthContextType {
  token: string | null;
  user: TokenPayload | null;
  tenantId: string | null;
  role: 'admin' | 'analyst' | 'developer' | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<LoginResponse>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<TokenPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('vigil_token');
    }
    setToken(null);
    setUser(null);
  }, []);

  // Initialize auth state from localStorage on mount
  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        const storedToken = localStorage.getItem('vigil_token');
        if (storedToken) {
          const decoded = decodeTokenPayload(storedToken);
          // 1-hour TTL expiration check
          if (decoded && decoded.exp * 1000 > Date.now()) {
            setToken(storedToken);
            setUser(decoded);
          } else {
            // Token expired
            logout();
          }
        }
      }
    } catch {
      logout();
    } finally {
      setIsLoading(false);
    }
  }, [logout]);

  const login = async (email: string, pass: string): Promise<LoginResponse> => {
    setIsLoading(true);
    try {
      const res = await api.login({ email, password: pass });
      if (res?.access_token) {
        if (typeof window !== 'undefined') {
          localStorage.setItem('vigil_token', res.access_token);
        }
        setToken(res.access_token);
        const decoded = decodeTokenPayload(res.access_token);
        setUser(decoded);
      }
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        tenantId: user?.tenant_id || null,
        role: user?.role || null,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
