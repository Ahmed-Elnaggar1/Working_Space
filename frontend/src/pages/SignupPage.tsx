import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { signup } from "../features/auth/api";
import { useAuth } from "../features/auth/useAuth";
import { SignupForm } from "../features/auth/components/SignupForm";
import { AuthLayout } from "../shared/layouts/AuthLayout";

export default function SignupPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { getErrorMessage } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(input: { email: string; password: string }) {
    setError(null);
    setIsSubmitting(true);
    try {
      await signup(input);
      navigate("/login", { replace: true, state: { registered: true } });
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Get started with Vault workspaces and channels"
      footer={
        <p>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      }
    >
      {location.state?.registered && (
        <p>Account created. You can now sign in.</p>
      )}
      <SignupForm
        onSubmit={handleSubmit}
        error={error}
        isSubmitting={isSubmitting}
      />
    </AuthLayout>
  );
}
