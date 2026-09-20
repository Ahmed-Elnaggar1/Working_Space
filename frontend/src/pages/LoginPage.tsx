import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/useAuth";
import { LoginForm } from "../features/auth/components/LoginForm";
import { AuthLayout } from "../shared/layouts/AuthLayout";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, getErrorMessage } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(input: { email: string; password: string }) {
    setError(null);
    setIsSubmitting(true);
    try {
      await login(input);
      navigate("/workspaces", { replace: true });
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your Vault workspace"
      footer={
        <p>
          Don't have an account? <Link to="/signup">Create an account</Link>
        </p>
      }
    >
      <LoginForm
        onSubmit={handleSubmit}
        error={error}
        isSubmitting={isSubmitting}
      />
    </AuthLayout>
  );
}
