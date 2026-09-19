import { useState, type SubmitEvent } from "react";
import styles from "../../../shared/layouts/AuthLayout/AuthLayout.module.css";

export function SignupForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    // Auth API integration will be added at the feature boundary.
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

      <button type="submit" className={styles.submitBtn}>
        Create Account
      </button>
    </form>
  );
}
