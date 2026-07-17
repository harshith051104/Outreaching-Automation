"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { forgotPassword, resetPassword } from "@/services/auth-api";
import { extractErrorMessage } from "@/utils/error";
import { Mail, Lock, Zap, ArrowRight, Eye, EyeOff, KeyRound } from "lucide-react";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [devCode, setDevCode] = useState("");

  const handleRequestCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const res = await forgotPassword(email);
      setMessage("A reset code has been generated. Please check your inbox (or see below).");
      if (res.code) {
        setDevCode(res.code); // Display it on screen for easy local developer experience
      }
      setStep(2);
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to request code"));
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    try {
      await resetPassword({
        email,
        code,
        new_password: newPassword,
      });
      setMessage("Password reset successful! Redirecting to login...");
      setTimeout(() => {
        router.push("/login");
      }, 2000);
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to reset password"));
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
            Reset your command center password
          </p>
        </div>

        {/* Form Card */}
        <div style={{
          background: 'rgba(22,17,50,0.85)',
          border: '1px solid rgba(124,92,255,0.2)',
          borderRadius: '20px',
          padding: '32px',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          boxShadow: '0 32px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
        }}>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: '#f5f3ff', margin: '0 0 6px' }}>
            {step === 1 ? "Forgot Password" : "Reset Password"}
          </h2>
          <p style={{ fontSize: '13px', color: 'rgba(167,139,250,0.7)', margin: '0 0 24px' }}>
            {step === 1 
              ? "Enter your email to receive a password reset code"
              : "Enter your reset code and set a new password"
            }
          </p>

          {error && (
            <div style={{
              padding: '12px 14px', borderRadius: '10px',
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
              color: '#f87171', fontSize: '13px', marginBottom: '16px',
            }}>
              {error}
            </div>
          )}

          {message && (
            <div style={{
              padding: '12px 14px', borderRadius: '10px',
              background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)',
              color: '#34d399', fontSize: '13px', marginBottom: '16px',
            }}>
              {message}
            </div>
          )}

          {step === 1 ? (
            <form onSubmit={handleRequestCode} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
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

              <button
                type="submit"
                disabled={loading}
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
                {loading ? "Generating code..." : "Send Reset Code"}
              </button>
            </form>
          ) : (
            <form onSubmit={handleResetPassword} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {devCode && (
                <div style={{
                  padding: '12px 14px', borderRadius: '10px',
                  background: 'rgba(124,92,255,0.15)', border: '1px dashed rgba(124,92,255,0.4)',
                  color: '#c084fc', fontSize: '13px', marginBottom: '8px',
                  textAlign: 'center', fontWeight: '600'
                }}>
                  Developer Reset Code: <span style={{ fontSize: '16px', color: '#e9d5ff', letterSpacing: '0.1em' }}>{devCode}</span>
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'rgba(167,139,250,0.8)', marginBottom: '8px', letterSpacing: '0.04em' }}>
                  VERIFICATION CODE
                </label>
                <div style={{ position: 'relative' }}>
                  <KeyRound size={15} color="rgba(167,139,250,0.5)" style={{ position: 'absolute', left: '13px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                  <input
                    type="text"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="Enter 6-digit code"
                    required
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
                  NEW PASSWORD
                </label>
                <div style={{ position: 'relative' }}>
                  <Lock size={15} color="rgba(167,139,250,0.5)" style={{ position: 'absolute', left: '13px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    required
                    minLength={8}
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
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                      background: 'none', border: 'none', cursor: 'pointer', display: 'flex',
                      alignItems: 'center', justifyContent: 'center', padding: '4px',
                      color: 'rgba(167,139,250,0.5)', transition: 'color 0.2s',
                    }}
                  >
                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
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
                {loading ? "Resetting password..." : "Reset Password"}
              </button>
            </form>
          )}
        </div>

        <p style={{ textAlign: 'center', marginTop: '20px', fontSize: '13px', color: 'rgba(167,139,250,0.6)' }}>
          Remember your password?{' '}
          <Link href="/login" style={{ color: '#a78bfa', textDecoration: 'none', fontWeight: '600' }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
