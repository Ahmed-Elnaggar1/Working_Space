import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { AuthLayout } from '../components/AuthLayout/AuthLayout';
import authStyles from '../components/AuthLayout/AuthLayout.module.css';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handled in S6-10 (calling POST /auth/login)
  };

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your Vault workspace"
      footer={
        <p>
          Don't have an account?{' '}
          <Link to="/signup">Create an account</Link>
        </p>
      }
    >
      <form className={authStyles.form} onSubmit={handleSubmit}>
        <div className={authStyles.inputGroup}>
          <label className={authStyles.label} htmlFor="login-email">
            Email address
          </label>
          <input
            id="login-email"
            type="email"
            className={authStyles.input}
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>

        <div className={authStyles.inputGroup}>
          <label className={authStyles.label} htmlFor="login-password">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            className={authStyles.input}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>

        <button type="submit" className={authStyles.submitBtn}>
          Sign In
        </button>
      </form>
    </AuthLayout>
  );
}
