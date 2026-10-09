import { useEffect, useRef, useState } from "react";
import { ApiError, getTokenProvider } from "../../../shared/api";
import { useAuth } from "../../auth/useAuth";
import {
  getChannel,
  getChannelFiles,
  getChannelMembers,
  getChannelWebSocketUrl,
  removeChannelMember,
  updateChannelMemberRole,
} from "../api";
import {
  canAskChannelBot,
  canSendChannelMessages,
  getWebSocketCloseErrorMessage,
  type WebSocketConnectionStatus,
} from "../chatManagement";
import {
  hasActiveIngestion,
  INGESTION_POLL_INTERVAL_MS,
} from "../fileManagement";
import {
  canManageChannelMembers,
  getMemberActionErrorMessage,
} from "../memberManagement";
import {
  getCachedChannelData,
  setCachedChannelData,
  updateCachedFiles,
  updateCachedMembers,
} from "../channelCache";
import type {
  Channel,
  ChannelFile,
  ChannelMember,
  ChannelMemberRole,
} from "../types";
import { FileList } from "./FileList";
import { FileUploadForm } from "./FileUploadForm";
import { InviteMemberForm } from "./InviteMemberForm";
import { MessageHistory } from "./MessageHistory";
import { BotAskPanel } from "./BotAskPanel";
import styles from "./ChannelShell.module.css";

interface ChannelShellProps {
  channelId: string;
  workspaceName?: string;
}

export function ChannelShell({ channelId, workspaceName }: ChannelShellProps) {
  const { user } = useAuth();

  // Initialize from cache if already loaded
  const cached = getCachedChannelData(channelId);
  const [channel, setChannel] = useState<Channel | null>(cached ? cached.channel : null);
  const [members, setMembers] = useState<ChannelMember[]>(cached ? cached.members : []);
  const [files, setFiles] = useState<ChannelFile[]>(cached ? cached.files : []);
  const [isLoading, setIsLoading] = useState(!cached);
  const [error, setError] = useState<string | null>(null);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [updatingMemberId, setUpdatingMemberId] = useState<string | null>(null);
  const [removingMemberId, setRemovingMemberId] = useState<string | null>(null);
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [socketStatus, setSocketStatus] =
    useState<WebSocketConnectionStatus>("connecting");
  const [socketError, setSocketError] = useState<string | null>(null);

  // Right-side contextual panel state
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true);
  const [rightPanelTab, setRightPanelTab] = useState<"info" | "bot">("info");

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // Sync cache on channelId change
  useEffect(() => {
    const cachedData = getCachedChannelData(channelId);
    if (cachedData) {
      setChannel(cachedData.channel);
      setMembers(cachedData.members);
      setFiles(cachedData.files);
      setIsLoading(false);
    } else {
      setChannel(null);
      setMembers([]);
      setFiles([]);
      setIsLoading(true);
    }
    setError(null);
    setRoleError(null);
    setRemoveError(null);
  }, [channelId]);

  // WebSocket lifecycle management (isolated to active channel)
  useEffect(() => {
    const tokenProvider = getTokenProvider();
    const token = tokenProvider ? tokenProvider() : null;

    if (!token) {
      return;
    }

    let isUnmounted = false;

    const connectSocket = () => {
      if (isUnmounted) {
        return;
      }

      const ws = new WebSocket(getChannelWebSocketUrl(channelId, token));
      socketRef.current = ws;
      setSocket(ws);
      setSocketStatus("connecting");
      setSocketError(null);

      ws.onopen = () => {
        if (reconnectTimeoutRef.current !== null) {
          window.clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
        setSocketStatus("connected");
        setSocketError(null);
      };

      ws.onclose = (event: CloseEvent) => {
        if (!isUnmounted) {
          setSocket(null);
          if (event.code === 1008) {
            setSocketStatus("rejected");
            setSocketError(getWebSocketCloseErrorMessage(1008));
            return;
          }
          setSocketStatus("disconnected");
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connectSocket();
          }, 1000);
        }
      };
    };

    connectSocket();

    return () => {
      isUnmounted = true;
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      setSocket(null);
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [channelId]);

  // Fetch channel details, members, and files
  useEffect(() => {
    let isMounted = true;

    async function loadChannel() {
      const cachedData = getCachedChannelData(channelId);
      if (!cachedData) {
        setIsLoading(true);
      }
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
          setCachedChannelData(channelId, {
            channel: channelResult,
            members: membersResult,
            files: filesResult,
          });
        }
      } catch (loadError) {
        if (isMounted && !cachedData) {
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

  // Active file ingestion status polling
  useEffect(() => {
    if (!hasActiveIngestion(files)) {
      return;
    }

    const intervalId = setInterval(async () => {
      try {
        const latestFiles = await getChannelFiles(channelId);
        setFiles(latestFiles);
        updateCachedFiles(channelId, latestFiles);
      } catch {
        // Silently preserve current files
      }
    }, INGESTION_POLL_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [channelId, files]);

  async function refreshMembers() {
    try {
      const result = await getChannelMembers(channelId);
      setMembers(result);
      updateCachedMembers(channelId, result);
    } catch {
      // Ignore
    }
  }

  function handleFileUploaded(newFile: ChannelFile) {
    setFiles((prev) => {
      const updated = [newFile, ...prev];
      updateCachedFiles(channelId, updated);
      return updated;
    });
  }

  function handleFileDeleted(fileId: string) {
    setFiles((prev) => {
      const updated = prev.filter((file) => file.id !== fileId);
      updateCachedFiles(channelId, updated);
      return updated;
    });
  }

  function handleFileUpdated(updatedFile: ChannelFile) {
    setFiles((prev) => {
      const updated = prev.map((file) =>
        file.id === updatedFile.id ? updatedFile : file,
      );
      updateCachedFiles(channelId, updated);
      return updated;
    });
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

  function openBotChat() {
    setRightPanelTab("bot");
    setIsRightPanelOpen(true);
  }

  function openChannelInfo(section?: "files" | "members") {
    setRightPanelTab("info");
    setIsRightPanelOpen(true);
    if (section) {
      const el = document.getElementById(`section-${section}`);
      el?.scrollIntoView({ behavior: "smooth" });
    }
  }

  const currentMember = members.find((member) => member.user_id === user?.id);
  const canManageMembers = canManageChannelMembers(currentMember?.role);
  const canSendMessages = canSendChannelMessages(currentMember?.role);
  const canAskBot = canAskChannelBot(currentMember?.role);

  // If initial load with no cached channel data, show middle panel skeleton
  if (isLoading && !channel) {
    return (
      <section className={styles.shell}>
        <header className={styles.channelHeader}>
          <div className={styles.headerTitleGroup}>
            <div className={styles.skeletonTitle} />
          </div>
        </header>
        <div className={styles.chatColumn}>
          <div className={styles.skeletonChat} />
        </div>
      </section>
    );
  }

  if (error && !channel) {
    return (
      <div className={styles.errorState}>
        <span className={styles.errorIcon}>⚠️</span>
        <h2>Unable to load channel</h2>
        <p className={styles.error}>{error}</p>
      </div>
    );
  }

  if (!channel) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.error}>Channel not found.</p>
      </div>
    );
  }

  return (
    <section className={styles.shell}>
      {/* Top Channel Header */}
      <header className={styles.channelHeader}>
        <div className={styles.headerTitleGroup}>
          <div className={styles.channelPrefix}>#</div>
          <div>
            <h1>{channel.name}</h1>
            {workspaceName && (
              <span className={styles.workspaceSubtitle}>in {workspaceName}</span>
            )}
          </div>
        </div>

        <div className={styles.headerToolbar}>
          {/* Connection status badge */}
          <div
            className={`${styles.connectionBadge} ${
              socketStatus === "connected"
                ? styles.connected
                : socketStatus === "disconnected"
                ? styles.offline
                : styles.connecting
            }`}
            title={`WebSocket status: ${socketStatus}`}
          >
            <span className={styles.statusDot} />
            <span className={styles.statusText}>{socketStatus}</span>
          </div>

          {/* Quick Action Buttons */}
          <button
            type="button"
            className={`${styles.toolbarButton} ${
              isRightPanelOpen && rightPanelTab === "bot" ? styles.activeBtn : ""
            }`}
            onClick={openBotChat}
            title="Open AI Bot Assistant"
          >
            <span>🤖</span>
            <span>Ask Bot</span>
          </button>

          <button
            type="button"
            className={`${styles.toolbarButton} ${
              isRightPanelOpen && rightPanelTab === "info" ? styles.activeBtn : ""
            }`}
            onClick={() => openChannelInfo("files")}
            title="View channel files"
          >
            <span>📁</span>
            <span>Files ({files.length})</span>
          </button>

          <button
            type="button"
            className={`${styles.toolbarButton} ${
              isRightPanelOpen && rightPanelTab === "info" ? styles.activeBtn : ""
            }`}
            onClick={() => openChannelInfo("members")}
            title="View channel members"
          >
            <span>👥</span>
            <span>Members ({members.length})</span>
          </button>

          {/* Toggle Panel Button */}
          <button
            type="button"
            className={`${styles.panelToggleButton} ${
              isRightPanelOpen ? styles.panelOpen : ""
            }`}
            onClick={() => setIsRightPanelOpen((prev) => !prev)}
            title={isRightPanelOpen ? "Collapse details panel" : "Open details panel"}
            aria-label="Toggle details panel"
          >
            {isRightPanelOpen ? "⇥" : "⇤"}
          </button>
        </div>
      </header>

      {/* Main Conversation & Composer (Middle Pane) */}
      <div className={styles.chatColumn}>
        <MessageHistory
          key={channelId}
          channelId={channelId}
          members={members}
          currentUserId={user?.id}
          socket={socket}
          socketStatus={socketStatus}
          socketError={socketError}
          canSendMessages={canSendMessages}
          canAskBot={canAskBot}
          onOpenBotChat={openBotChat}
          onOpenFileUpload={() => openChannelInfo("files")}
        />
      </div>

      {/* Contextual & Collapsible Right Panel */}
      {isRightPanelOpen && (
        <aside
          className={styles.detailsColumn}
          aria-label="Channel contextual information"
        >
          {/* Panel Header & Tabs */}
          <div className={styles.panelHeader}>
            <div className={styles.panelTabs} role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={rightPanelTab === "info"}
                className={`${styles.panelTab} ${
                  rightPanelTab === "info" ? styles.activeTab : ""
                }`}
                onClick={() => setRightPanelTab("info")}
              >
                <span>ℹ️</span>
                <span>Channel Info</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={rightPanelTab === "bot"}
                className={`${styles.panelTab} ${
                  rightPanelTab === "bot" ? styles.activeTab : ""
                }`}
                onClick={() => setRightPanelTab("bot")}
              >
                <span>🤖</span>
                <span>Bot Assistant</span>
              </button>
            </div>
            <button
              type="button"
              className={styles.closePanelButton}
              onClick={() => setIsRightPanelOpen(false)}
              title="Close panel"
              aria-label="Close panel"
            >
              ×
            </button>
          </div>

          {/* Tab 1: Channel Info (Details, Files, Members) */}
          {rightPanelTab === "info" && (
            <div className={styles.panelContent}>
              <div className={styles.section}>
                <h2>Channel Overview</h2>
                <div className={styles.channelDetails}>
                  <p className={styles.channelDetailsName}># {channel.name}</p>
                  <p>
                    Created {new Date(channel.created_at).toLocaleDateString()}
                  </p>
                  <p>
                    {members.length} {members.length === 1 ? "member" : "members"}
                    {" • "}
                    {files.length} {files.length === 1 ? "file" : "files"}
                  </p>
                </div>
              </div>

              <div id="section-files" className={styles.section}>
                <div className={styles.sectionHeader}>
                  <h2>Files</h2>
                  <span className={styles.sectionCount}>{files.length}</span>
                </div>
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

              <div id="section-members" className={styles.section}>
                <div className={styles.sectionHeader}>
                  <h2>Members</h2>
                  <span className={styles.sectionCount}>{members.length}</span>
                </div>

                {canManageMembers && (
                  <InviteMemberForm
                    channelId={channelId}
                    onInvited={refreshMembers}
                  />
                )}

                {roleError && <p className={styles.error}>{roleError}</p>}
                {removeError && <p className={styles.error}>{removeError}</p>}

                {members.length === 0 ? (
                  <p className={styles.status}>
                    No members found for this channel.
                  </p>
                ) : (
                  <ul className={styles.memberList}>
                    {members.map((member) => (
                      <li key={member.id} className={styles.memberItem}>
                        <div className={styles.memberInfo}>
                          <div className={styles.memberAvatar}>
                            {(member.username ?? member.email)
                              .slice(0, 2)
                              .toUpperCase()}
                          </div>
                          <div>
                            <p className={styles.memberEmail}>{member.email}</p>
                            {member.username && (
                              <p className={styles.memberUsername}>
                                @{member.username}
                              </p>
                            )}
                          </div>
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
                                void handleRemoveMember(
                                  member.user_id,
                                  member.email,
                                )
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
            </div>
          )}

          {/* Tab 2: Bot Assistant */}
          {rightPanelTab === "bot" && (
            <div className={styles.botPanelWrapper}>
              <BotAskPanel channelId={channelId} />
            </div>
          )}
        </aside>
      )}
    </section>
  );
}
