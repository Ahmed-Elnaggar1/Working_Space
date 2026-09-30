import { useState, type SubmitEvent } from "react";
import { ApiError } from "../../../shared/api";
import { createChannel } from "../api";
import type { ChannelCreateInput } from "../types";
import styles from "./CreateChannelForm.module.css";

interface CreateChannelFormProps {
  workspaceId: string;
  onCreated: () => void;
}

export function CreateChannelForm({
  workspaceId,
  onCreated,
}: CreateChannelFormProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const input: ChannelCreateInput = { name: name.trim() };

    setError(null);
    setIsSubmitting(true);

    try {
      await createChannel(workspaceId, input);
      setName("");
      onCreated();
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "Unable to create channel. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <label className={styles.label} htmlFor="channel-name">
        Create channel
      </label>
      <div className={styles.controls}>
        <input
          id="channel-name"
          className={styles.input}
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Channel name"
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
