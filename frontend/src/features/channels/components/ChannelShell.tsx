import { useEffect, useState } from "react";
import { ApiError } from "../../../shared/api";
import { useAuth } from "../../auth/useAuth";
import {
  getChannel,
  getChannelFiles,
  getChannelMembers,
  removeChannelMember,
  updateChannelMemberRole,
} from "../api";
import {
  hasActiveIngestion,
  INGESTION_POLL_INTERVAL_MS,
} from "../fileManagement";
import {
  canManageChannelMembers,
  getMemberActionErrorMessage,
} from "../memberManagement";
import type {
  Channel,
  ChannelFile,
  ChannelMember,
  ChannelMemberRole,
} from "../types";
import { BotAskPanel } from "./BotAskPanel";
import { FileList } from "./FileList";
import { FileUploadForm } from "./FileUploadForm";
import { InviteMemberForm } from "./InviteMemberForm";
import styles from "./ChannelShell.module.css";

interface ChannelShellProps {
  channelId: string;
}

export function ChannelShell({ channelId }: ChannelShellProps) {
  const { user } = useAuth();
  const [channel, setChannel] = useState<Channel | null>(null);
  const [members, setMembers] = useState<ChannelMember[]>([]);
  const [files, setFiles] = useState<ChannelFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [updatingMemberId, setUpdatingMemberId] = useState<string | null>(null);
  const [removingMemberId, setRemovingMemberId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadChannel() {
      setIsLoading(true);
      setError(null);

      try {
        const [channelResult, membersResult, filesResult] = await Promise.all([
          getChannel(channelId),
          getChannelMembers(channelId),
          getChannelFiles(channelId),
        ]);
        if (isMounted) {
          setChannel(channelResult);
          setMembers(membersResult);
          setFiles(filesResult);
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

  // S7-06: Ingestion status polling while any file is pending or processing
  useEffect(() => {
    if (!hasActiveIngestion(files)) {
      return;
    }

    const intervalId = setInterval(async () => {
      try {
        const latestFiles = await getChannelFiles(channelId);
        setFiles(latestFiles);
      } catch {
        // Silently preserve current files on intermittent poll failure
      }
    }, INGESTION_POLL_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [channelId, files]);

  async function refreshMembers() {
    const result = await getChannelMembers(channelId);
    setMembers(result);
  }

  function handleFileUploaded(newFile: ChannelFile) {
    setFiles((prev) => [newFile, ...prev]);
  }

  function handleFileDeleted(fileId: string) {
    setFiles((prev) => prev.filter((file) => file.id !== fileId));
  }

  function handleFileUpdated(updatedFile: ChannelFile) {
    setFiles((prev) =>
      prev.map((file) => (file.id === updatedFile.id ? updatedFile : file)),
    );
  }

  async function handleRoleChange(userId: string, role: ChannelMemberRole) {
    setRoleError(null);
    setUpdatingMemberId(userId);

    try {
      await updateChannelMemberRole(channelId, userId, { role });
      await refreshMembers();
    } catch (roleChangeError) {
      setRoleError(getMemberActionErrorMessage("change_role", roleChangeError));
    } finally {
      setUpdatingMemberId(null);
    }
  }

  async function handleRemoveMember(userId: string, email: string) {
    if (!window.confirm(`Remove ${email} from this channel?`)) {
      return;
    }

    setRemoveError(null);
    setRemovingMemberId(userId);

    try {
      await removeChannelMember(channelId, userId);
      await refreshMembers();
    } catch (removeMemberError) {
      setRemoveError(getMemberActionErrorMessage("remove", removeMemberError));
    } finally {
      setRemovingMemberId(null);
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
  const canManageMembers = canManageChannelMembers(currentMember?.role);

  return (
    <section className={styles.shell}>
      <p className={styles.eyebrow}>Channel</p>
      <h1>{channel.name}</h1>

      <div className={styles.section}>
        <h2>Files</h2>
        <FileUploadForm
          channelId={channelId}
          userRole={currentMember?.role}
          onUploaded={handleFileUploaded}
        />
        <FileList
          channelId={channelId}
          files={files}
          members={members}
          currentUserId={user?.id}
          currentUserRole={currentMember?.role}
          onFileDeleted={handleFileDeleted}
          onFileUpdated={handleFileUpdated}
        />
      </div>

      <div className={styles.section}>
        <BotAskPanel key={channelId} channelId={channelId} />
      </div>

      <div className={styles.section}>
        <h2>Members</h2>

        {canManageMembers && (
          <InviteMemberForm channelId={channelId} onInvited={refreshMembers} />
        )}

        {roleError && <p className={styles.error}>{roleError}</p>}
        {removeError && <p className={styles.error}>{removeError}</p>}

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
                  <div className={styles.memberActions}>
                    <select
                      className={styles.roleSelect}
                      value={member.role}
                      aria-label={`Role for ${member.email}`}
                      disabled={
                        updatingMemberId === member.user_id ||
                        removingMemberId === member.user_id
                      }
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
                    <button
                      className={styles.removeButton}
                      type="button"
                      disabled={
                        updatingMemberId === member.user_id ||
                        removingMemberId === member.user_id
                      }
                      onClick={() =>
                        void handleRemoveMember(member.user_id, member.email)
                      }
                    >
                      {removingMemberId === member.user_id
                        ? "Removing..."
                        : "Remove"}
                    </button>
                  </div>
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
