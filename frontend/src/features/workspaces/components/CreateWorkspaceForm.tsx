import { useState, type SubmitEvent } from "react";
import { ApiError } from "../../../shared/api";
import { createWorkspace } from "../api";
import type { Workspace, WorkspaceCreateInput } from "../types";
import styles from "./CreateWorkspaceForm.module.css";

interface CreateWorkspaceFormProps {
  onCreated: (workspace?: Workspace) => void;
}

export function CreateWorkspaceForm({ onCreated }: CreateWorkspaceFormProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const input: WorkspaceCreateInput = { name: name.trim() };

    setError(null);
    setIsSubmitting(true);

    try {
      const workspace = await createWorkspace(input);
      setName("");
      onCreated(workspace);
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "Unable to create workspace. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <label className={styles.label} htmlFor="workspace-name">
        Create workspace
      </label>
      <div className={styles.controls}>
        <input
          id="workspace-name"
          className={styles.input}
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Workspace name"
          minLength={1}
          maxLength={255}
          required
        />
        <button type="submit" className={styles.button} disabled={isSubmitting}>
          {isSubmitting ? "Creating..." : "Create"}
        </button>
      </div>
      {error && <p className={styles.error}>{error}</p>}
    </form>
  );
}
