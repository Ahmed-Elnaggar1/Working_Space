import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { AuthLayout } from '../components/AuthLayout/AuthLayout';
import authStyles from '../components/AuthLayout/AuthLayout.module.css';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handled in S6-09 (calling POST /auth/signup)
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Get started with Vault workspaces and channels"
      footer={
        <p>
          Already have an account?{' '}
          <Link to="/login">Sign in</Link>
        </p>
      }
    >
      <form className={authStyles.form} onSubmit={handleSubmit}>
        <div className={authStyles.inputGroup}>
          <label className={authStyles.label} htmlFor="signup-email">
            Email address
          </label>
          <input
            id="signup-email"
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
          <label className={authStyles.label} htmlFor="signup-password">
            Password (min 8 characters)
          </label>
          <input
            id="signup-password"
            type="password"
            className={authStyles.input}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
        </div>

        <button type="submit" className={authStyles.submitBtn}>
          Create Account
        </button>
      </form>
    </AuthLayout>
  );
}
