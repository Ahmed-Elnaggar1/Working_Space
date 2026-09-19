import { useState, type SubmitEvent } from "react";
import styles from "../../../shared/layouts/AuthLayout/AuthLayout.module.css";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    // Auth API integration will be added at the feature boundary.
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.inputGroup}>
        <label className={styles.label} htmlFor="login-email">
          Email address
        </label>
        <input
          id="login-email"
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
        <label className={styles.label} htmlFor="login-password">
          Password
        </label>
        <input
          id="login-password"
          type="password"
          className={styles.input}
          placeholder="••••••••"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          autoComplete="current-password"
        />
      </div>

      <button type="submit" className={styles.submitBtn}>
        Sign In
      </button>
    </form>
  );
}
