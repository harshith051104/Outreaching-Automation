"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/services/auth-api";
import { useAuthStore } from "@/store/auth-store";
import { extractErrorMessage } from "@/utils/error";
import { Mail, Lock, Zap, ArrowRight, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { setUser, setToken } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login({ email, password });
      setToken(data.access_token);
      setUser(data.user);
      router.push("/dashboard");
    } catch (err: any) {
      setError(extractErrorMessage(err, "Login failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(145deg, #060413 0%, #0d0823 50%, #120a2e 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
    }}>
      {/* Background orbs */}
      <div style={{ position: 'absolute', top: '-100px', left: '-100px', width: '500px', height: '500px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(124,92,255,0.15) 0%, transparent 70%)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: '-100px', right: '-100px', width: '600px', height: '600px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,102,241,0.1) 0%, transparent 70%)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: '40%', right: '20%', width: '300px', height: '300px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(16,185,129,0.06) 0%, transparent 70%)', pointerEvents: 'none' }} />
      
      {/* Grid overlay */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'linear-gradient(rgba(124,92,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(124,92,255,0.04) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
        pointerEvents: 'none',
      }} />

      {/* Card */}
      <div style={{
        width: '100%', maxWidth: '420px', padding: '16px',
        position: 'relative', zIndex: 1,
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '16px',
            background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 8px 32px rgba(124,92,255,0.4)',
          }}>
            <Zap size={26} color="white" strokeWidth={2.5} />
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: '800', color: '#f5f3ff', margin: '0 0 4px', letterSpacing: '-0.02em' }}>
            AI Outreach Platform
          </h1>
          <p style={{ fontSize: '13px', color: 'rgba(167,139,250,0.7)', margin: 0 }}>
            Command your sales pipeline with AI
          </p>
        </div>

        {/* Login Card */}
        <div style={{
          background: 'rgba(22,17,50,0.85)',
          border: '1px solid rgba(124,92,255,0.2)',
          borderRadius: '20px',
          padding: '32px',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          boxShadow: '0 32px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
        }}>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: '#f5f3ff', margin: '0 0 6px' }}>Welcome back</h2>
          <p style={{ fontSize: '13px', color: 'rgba(167,139,250,0.7)', margin: '0 0 24px' }}>Sign in to your command center</p>

          {error && (
            <div style={{
              padding: '12px 14px', borderRadius: '10px',
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
              color: '#f87171', fontSize: '13px', marginBottom: '16px',
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'rgba(167,139,250,0.8)', marginBottom: '8px', letterSpacing: '0.04em' }}>
                EMAIL ADDRESS
              </label>
              <div style={{ position: 'relative' }}>
                <Mail size={15} color="rgba(167,139,250,0.5)" style={{ position: 'absolute', left: '13px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  suppressHydrationWarning
                  style={{
                    width: '100%', padding: '11px 14px 11px 38px',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(124,92,255,0.2)',
                    borderRadius: '10px', color: '#f5f3ff',
                    fontSize: '14px', fontFamily: 'inherit',
                    outline: 'none', boxSizing: 'border-box',
                    transition: 'border-color 0.2s, box-shadow 0.2s',
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(124,92,255,0.6)'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(124,92,255,0.12)'; }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'rgba(124,92,255,0.2)'; e.currentTarget.style.boxShadow = 'none'; }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'rgba(167,139,250,0.8)', marginBottom: '8px', letterSpacing: '0.04em' }}>
                PASSWORD
              </label>
              <div style={{ position: 'relative' }}>
                <Lock size={15} color="rgba(167,139,250,0.5)" style={{ position: 'absolute', left: '13px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your password"
                  required
                  suppressHydrationWarning
                  style={{
                    width: '100%', padding: '11px 40px 11px 38px',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(124,92,255,0.2)',
                    borderRadius: '10px', color: '#f5f3ff',
                    fontSize: '14px', fontFamily: 'inherit',
                    outline: 'none', boxSizing: 'border-box',
                    transition: 'border-color 0.2s, box-shadow 0.2s',
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(124,92,255,0.6)'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(124,92,255,0.12)'; }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'rgba(124,92,255,0.2)'; e.currentTarget.style.boxShadow = 'none'; }}
                />
                <button
                  type="button"
                  suppressHydrationWarning
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '4px',
                    color: 'rgba(167,139,250,0.5)',
                    transition: 'color 0.2s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.color = '#a78bfa'}
                  onMouseLeave={e => e.currentTarget.style.color = 'rgba(167,139,250,0.5)'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              suppressHydrationWarning
              style={{
                width: '100%', padding: '12px',
                borderRadius: '10px', border: 'none',
                background: loading ? 'rgba(124,92,255,0.5)' : 'linear-gradient(135deg, #7c5cff, #6344d9)',
                color: 'white', fontSize: '14px', fontWeight: '700',
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                boxShadow: loading ? 'none' : '0 4px 20px rgba(124,92,255,0.4)',
                transition: 'all 0.2s ease',
                marginTop: '4px',
              }}
            >
              {loading ? (
                <>
                  <div style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                  Signing in...
                </>
              ) : (
                <>
                  Sign In <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
        </div>

        <p style={{ textAlign: 'center', marginTop: '20px', fontSize: '13px', color: 'rgba(167,139,250,0.6)' }}>
          Don&apos;t have an account?{' '}
          <Link href="/register" style={{ color: '#a78bfa', textDecoration: 'none', fontWeight: '600' }}>
            Sign up
          </Link>
        </p>

        <style>{`
          @keyframes spin { to { transform: rotate(360deg); } }
          input::placeholder { color: rgba(167,139,250,0.35); }
        `}</style>
      </div>
    </div>
  );
}