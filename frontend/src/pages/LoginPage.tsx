import { Link } from "react-router-dom";
import { LoginForm } from "../features/auth/components/LoginForm";
import { AuthLayout } from "../shared/layouts/AuthLayout";

export default function LoginPage() {
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
      <LoginForm />
    </AuthLayout>
  );
}
