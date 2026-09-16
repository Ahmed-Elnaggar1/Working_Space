import { Link } from 'react-router-dom';

export default function WorkspacesPage() {
  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '1.75rem', marginBottom: '1rem' }}>Workspaces</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
        Workspace listing and channel navigation will be connected in S6-14 & S6-16.
      </p>
      <Link to="/login">← Back to Login</Link>
    </div>
  );
}
