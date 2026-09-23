import { useState, type SubmitEvent } from "react";
import styles from "../../../shared/layouts/AuthLayout/AuthLayout.module.css";
import type { SignupInput } from "../types";

interface SignupFormProps {
  onSubmit: (input: SignupInput) => Promise<void>;
  error: string | null;
  isSubmitting: boolean;
}

export function SignupForm({ onSubmit, error, isSubmitting }: SignupFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({ email, password });
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.inputGroup}>
        <label className={styles.label} htmlFor="signup-email">
          Email address
        </label>
        <input
          id="signup-email"
          type="email"
          className={styles.input}
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          autoComplete="email"
        />
      </div>

      <div className={styles.inputGroup}>
        <label className={styles.label} htmlFor="signup-password">
          Password (min 8 characters)
        </label>
        <input
          id="signup-password"
          type="password"
          className={styles.input}
          placeholder="••••••••"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          minLength={8}
          autoComplete="new-password"
        />
      </div>

      {error && <p className={styles.error}>{error}</p>}

      <button
        type="submit"
        className={styles.submitBtn}
        disabled={isSubmitting}
      >
        {isSubmitting ? "Creating Account..." : "Create Account"}
      </button>
    </form>
  );
}
