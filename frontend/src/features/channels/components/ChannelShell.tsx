import { useEffect, useState } from "react";
import { ApiError } from "../../../shared/api";
import { useAuth } from "../../auth/useAuth";
import { getChannel, getChannelMembers, updateChannelMemberRole } from "../api";
import type { Channel, ChannelMember, ChannelMemberRole } from "../types";
import { InviteMemberForm } from "./InviteMemberForm";
import styles from "./ChannelShell.module.css";

interface ChannelShellProps {
  channelId: string;
}

export function ChannelShell({ channelId }: ChannelShellProps) {
  const { user } = useAuth();
  const [channel, setChannel] = useState<Channel | null>(null);
  const [members, setMembers] = useState<ChannelMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [updatingMemberId, setUpdatingMemberId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadChannel() {
      setIsLoading(true);
      setError(null);

      try {
        const [channelResult, membersResult] = await Promise.all([
          getChannel(channelId),
          getChannelMembers(channelId),
        ]);
        if (isMounted) {
          setChannel(channelResult);
          setMembers(membersResult);
        }
      } catch (loadError) {
        if (isMounted) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load this channel. Please try again.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadChannel();

    return () => {
      isMounted = false;
    };
  }, [channelId]);

  async function refreshMembers() {
    const result = await getChannelMembers(channelId);
    setMembers(result);
  }

  async function handleRoleChange(userId: string, role: ChannelMemberRole) {
    setRoleError(null);
    setUpdatingMemberId(userId);

    try {
      await updateChannelMemberRole(channelId, userId, { role });
      await refreshMembers();
    } catch (roleChangeError) {
      setRoleError(
        roleChangeError instanceof ApiError
          ? roleChangeError.message
          : "Unable to update this member's role. Please try again.",
      );
    } finally {
      setUpdatingMemberId(null);
    }
  }

  if (isLoading) {
    return <p className={styles.status}>Loading channel...</p>;
  }

  if (error) {
    return <p className={styles.error}>{error}</p>;
  }

  if (!channel) {
    return <p className={styles.error}>Channel not found.</p>;
  }

  const currentMember = members.find((member) => member.user_id === user?.id);
  const canManageMembers =
    currentMember?.role === "owner" || currentMember?.role === "admin";

  return (
    <section className={styles.shell}>
      <p className={styles.eyebrow}>Channel</p>
      <h1>{channel.name}</h1>
      <div className={styles.section}>
        <h2>Members</h2>

        {canManageMembers && (
          <InviteMemberForm channelId={channelId} onInvited={refreshMembers} />
        )}

        {roleError && <p className={styles.error}>{roleError}</p>}

        {members.length === 0 ? (
          <p className={styles.status}>No members found for this channel.</p>
        ) : (
          <ul className={styles.memberList}>
            {members.map((member) => (
              <li key={member.id} className={styles.memberItem}>
                <div>
                  <p className={styles.memberEmail}>{member.email}</p>
                </div>
                {canManageMembers ? (
                  <select
                    className={styles.roleSelect}
                    value={member.role}
                    aria-label={`Role for ${member.email}`}
                    disabled={updatingMemberId === member.user_id}
                    onChange={(event) =>
                      void handleRoleChange(
                        member.user_id,
                        event.target.value as ChannelMemberRole,
                      )
                    }
                  >
                    <option value="owner">Owner</option>
                    <option value="admin">Admin</option>
                    <option value="member">Member</option>
                    <option value="read_only">Read only</option>
                  </select>
                ) : (
                  <span className={styles.roleBadge}>{member.role}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
