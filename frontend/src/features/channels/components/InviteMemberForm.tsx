import { useState, type FormEvent } from "react";
import { addChannelMember } from "../api";
import { getMemberActionErrorMessage } from "../memberManagement";
import styles from "./InviteMemberForm.module.css";

interface InviteMemberFormProps {
  channelId: string;
  onInvited: () => Promise<void>;
}

export function InviteMemberForm({
  channelId,
  onInvited,
}: InviteMemberFormProps) {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);

    try {
      await addChannelMember(channelId, { email, role: "member" });
      await onInvited();
      setEmail("");
      setSuccess("Member invited successfully.");
    } catch (inviteError) {
      setError(getMemberActionErrorMessage("invite", inviteError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <label className={styles.label} htmlFor="member-email">
        Invite by email
      </label>
      <div className={styles.controls}>
        <input
          id="member-email"
          className={styles.input}
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="person@example.com"
          required
          disabled={isSubmitting}
        />
        <button className={styles.button} type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Inviting..." : "Invite member"}
        </button>
      </div>
      {error && <p className={styles.error}>{error}</p>}
      {success && <p className={styles.success}>{success}</p>}
    </form>
  );
}
