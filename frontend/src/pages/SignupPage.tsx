import { Link } from "react-router-dom";
import { SignupForm } from "../features/auth/components/SignupForm";
import { AuthLayout } from "../shared/layouts/AuthLayout";

export default function SignupPage() {
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
      <SignupForm />
    </AuthLayout>
  );
}
