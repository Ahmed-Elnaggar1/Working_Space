import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../../shared/api";
import { useAuth } from "../../auth/useAuth";
import { getWorkspaceChannels, getWorkspaces } from "../api";
import type { Channel, Workspace } from "../types";
import { CreateChannelForm } from "./CreateChannelForm";
import { CreateWorkspaceForm } from "./CreateWorkspaceForm";
import { ChannelShell } from "../../channels/components/ChannelShell";
import {
  addCachedChannel,
  addCachedWorkspace,
  getCachedWorkspaceChannels,
  getCachedWorkspaces,
  prefetchChannel,
  prefetchWorkspaceChannels,
  setCachedWorkspaceChannels,
  setCachedWorkspaces,
} from "../../channels/channelCache";
import {
  NotificationsProvider,
  NotificationBell,
  NotificationInbox,
} from "../../notifications";
import styles from "./WorkspaceShell.module.css";

export function WorkspaceShell() {
  const navigate = useNavigate();
  const { workspaceId: routeWorkspaceId, channelId: routeChannelId } =
    useParams<{ workspaceId?: string; channelId?: string }>();
  const { user, logout } = useAuth();

  // In-memory initialized state
  const cachedWs = getCachedWorkspaces();
  const [workspaces, setWorkspaces] = useState<Workspace[]>(cachedWs ?? []);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>(
    routeWorkspaceId ?? (cachedWs && cachedWs[0] ? cachedWs[0].id : ""),
  );

  const cachedChs = selectedWorkspaceId
    ? getCachedWorkspaceChannels(selectedWorkspaceId)
    : undefined;
  const [channels, setChannels] = useState<Channel[]>(cachedChs ?? []);
  const [selectedChannelId, setSelectedChannelId] = useState<string>(
    routeChannelId ?? (cachedChs && cachedChs[0] ? cachedChs[0].id : ""),
  );

  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(!cachedWs);
  const [isLoadingChannels, setIsLoadingChannels] = useState(
    Boolean(selectedWorkspaceId && !cachedChs),
  );
  const [error, setError] = useState<string | null>(null);
  const [showCreateWorkspace, setShowCreateWorkspace] = useState(false);
  const [showCreateChannel, setShowCreateChannel] = useState(false);

  // 1. Load workspaces once (in-memory cached)
  useEffect(() => {
    let mounted = true;

    async function loadWorkspaces() {
      const cached = getCachedWorkspaces();
      if (!cached) {
        setIsLoadingWorkspaces(true);
      }

      try {
        const result = await getWorkspaces();
        if (!mounted) return;
        setWorkspaces(result);
        setCachedWorkspaces(result);

        // Auto-select workspace if none is selected
        if (result.length > 0) {
          const matched = routeWorkspaceId
            ? result.find((w) => w.id === routeWorkspaceId)
            : undefined;
          const targetWs = matched ?? result[0];

          if (selectedWorkspaceId !== targetWs.id) {
            setSelectedWorkspaceId(targetWs.id);
          }
        }
      } catch (loadError) {
        if (mounted && !cached) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load workspaces.",
          );
        }
      } finally {
        if (mounted) setIsLoadingWorkspaces(false);
      }
    }

    void loadWorkspaces();

    return () => {
      mounted = false;
    };
  }, []);

  // 2. React to routeWorkspaceId changes
  useEffect(() => {
    if (routeWorkspaceId && routeWorkspaceId !== selectedWorkspaceId) {
      setSelectedWorkspaceId(routeWorkspaceId);
    }
  }, [routeWorkspaceId, selectedWorkspaceId]);

  // 3. React to routeChannelId changes
  useEffect(() => {
    if (routeChannelId && routeChannelId !== selectedChannelId) {
      setSelectedChannelId(routeChannelId);
    }
  }, [routeChannelId, selectedChannelId]);

  // 4. Load channels when selectedWorkspaceId changes (using cache when available)
  useEffect(() => {
    if (!selectedWorkspaceId) {
      setChannels([]);
      return;
    }

    let mounted = true;
    const cachedChannels = getCachedWorkspaceChannels(selectedWorkspaceId);

    if (cachedChannels) {
      setChannels(cachedChannels);
      setIsLoadingChannels(false);

      // Determine active channel
      const targetChannelId =
        routeChannelId && cachedChannels.some((c) => c.id === routeChannelId)
          ? routeChannelId
          : cachedChannels[0]?.id ?? "";

      setSelectedChannelId(targetChannelId);

      // Keep URL synchronized if needed
      if (targetChannelId && targetChannelId !== routeChannelId) {
        navigate(
          `/workspaces/${selectedWorkspaceId}/channels/${targetChannelId}`,
          { replace: true },
        );
      }
    } else {
      setIsLoadingChannels(true);
    }

    // Always fetch fresh channels in background or if uncached
    void getWorkspaceChannels(selectedWorkspaceId)
      .then((result) => {
        if (!mounted) return;
        setChannels(result);
        setCachedWorkspaceChannels(selectedWorkspaceId, result);

        const targetChannelId =
          routeChannelId && result.some((c) => c.id === routeChannelId)
            ? routeChannelId
            : result[0]?.id ?? "";

        setSelectedChannelId(targetChannelId);

        if (targetChannelId && targetChannelId !== routeChannelId) {
          navigate(
            `/workspaces/${selectedWorkspaceId}/channels/${targetChannelId}`,
            { replace: true },
          );
        }
      })
      .catch((loadError) => {
        if (mounted && !cachedChannels) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load channels.",
          );
        }
      })
      .finally(() => {
        if (mounted) setIsLoadingChannels(false);
      });

    return () => {
      mounted = false;
    };
  }, [selectedWorkspaceId, routeChannelId, navigate]);

  // 5. Handle legacy direct /channels/:channelId route lookup
  useEffect(() => {
    if (routeChannelId && !routeWorkspaceId && workspaces.length > 0) {
      // Find workspace that contains this channel
      for (const ws of workspaces) {
        const cached = getCachedWorkspaceChannels(ws.id);
        if (cached && cached.some((c) => c.id === routeChannelId)) {
          setSelectedWorkspaceId(ws.id);
          navigate(`/workspaces/${ws.id}/channels/${routeChannelId}`, {
            replace: true,
          });
          return;
        }
      }
    }
  }, [routeChannelId, routeWorkspaceId, workspaces, navigate]);

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId),
    [selectedWorkspaceId, workspaces],
  );

  function selectWorkspace(workspaceId: string) {
    if (workspaceId === selectedWorkspaceId) return;

    setSelectedWorkspaceId(workspaceId);
    const cachedChannels = getCachedWorkspaceChannels(workspaceId);

    if (cachedChannels && cachedChannels.length > 0) {
      const firstChannel = cachedChannels[0];
      setSelectedChannelId(firstChannel.id);
      navigate(`/workspaces/${workspaceId}/channels/${firstChannel.id}`);
    } else {
      setSelectedChannelId("");
      setIsLoadingChannels(true);
      navigate(`/workspaces/${workspaceId}`);
    }
  }

  function selectChannel(channelId: string) {
    if (channelId === selectedChannelId) return;

    setSelectedChannelId(channelId);
    if (selectedWorkspaceId) {
      navigate(`/workspaces/${selectedWorkspaceId}/channels/${channelId}`);
    }
  }

  function handleWorkspaceCreated(workspace?: Workspace) {
    if (!workspace) return;
    setWorkspaces((current) => [...current, workspace]);
    addCachedWorkspace(workspace);
    setShowCreateWorkspace(false);
    selectWorkspace(workspace.id);
  }

  function handleChannelCreated(channel?: Channel) {
    if (!channel) return;
    setChannels((current) => [...current, channel]);
    if (selectedWorkspaceId) {
      addCachedChannel(selectedWorkspaceId, channel);
    }
    setShowCreateChannel(false);
    selectChannel(channel.id);
  }

  return (
    <NotificationsProvider>
      <div className={styles.app}>
      {/* 1. Left Workspace Rail */}
      <aside className={styles.workspaceRail} aria-label="Workspaces Rail">
        <div className={styles.railTop}>
          <div className={styles.brand} title="Working Space">
            <span>WS</span>
          </div>
          <div className={styles.railDivider} />
        </div>

        <nav className={styles.workspaceList} aria-label="Workspaces list">
          {isLoadingWorkspaces && workspaces.length === 0 ? (
            <div className={styles.railSkeletonGroup}>
              <div className={styles.railSkeleton} />
              <div className={styles.railSkeleton} />
            </div>
          ) : (
            workspaces.map((workspace) => {
              const isActive = workspace.id === selectedWorkspaceId;
              return (
                <div key={workspace.id} className={styles.workspaceItemWrapper}>
                  {/* Discord-style active indicator pill */}
                  <div
                    className={`${styles.activePill} ${
                      isActive ? styles.pillActive : ""
                    }`}
                  />
                  <button
                    className={`${styles.workspaceButton} ${
                      isActive ? styles.activeWorkspace : ""
                    }`}
                    type="button"
                    title={workspace.name}
                    aria-label={`Workspace: ${workspace.name}`}
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => selectWorkspace(workspace.id)}
                    onMouseEnter={() => prefetchWorkspaceChannels(workspace.id)}
                  >
                    {workspace.name.slice(0, 2).toUpperCase()}
                  </button>
                </div>
              );
            })
          )}

          <div className={styles.workspaceItemWrapper}>
            <div className={styles.activePill} />
            <button
              className={styles.addButton}
              type="button"
              onClick={() => setShowCreateWorkspace(true)}
              aria-label="Create workspace"
              title="Add a workspace"
            >
              +
            </button>
          </div>
        </nav>

        {/* User profile, Notifications, & Logout at bottom of rail */}
        <div className={styles.railBottom}>
          <NotificationBell />
          <div
            className={styles.userAvatar}
            title={user?.email ?? "User Profile"}
          >
            {(user?.username ?? user?.email ?? "U").slice(0, 2).toUpperCase()}
          </div>
          <button
            className={styles.logoutButton}
            type="button"
            onClick={() =>
              void logout().then(() => navigate("/login", { replace: true }))
            }
            title="Log out"
            aria-label="Log out"
          >
            ↪
          </button>
        </div>
      </aside>

      {/* 2. Channel Sidebar (Second Column) */}
      <aside className={styles.channelSidebar} aria-label="Channels Sidebar">
        <header className={styles.sidebarHeader}>
          <div className={styles.workspaceInfo}>
            <h2 className={styles.workspaceName}>
              {selectedWorkspace?.name ?? "Workspaces"}
            </h2>
          </div>
          <button
            type="button"
            className={styles.createChannelBtn}
            onClick={() => setShowCreateChannel((current) => !current)}
            aria-label="Create channel"
            title="Create a new channel"
          >
            +
          </button>
        </header>

        {showCreateChannel && selectedWorkspaceId && (
          <div className={styles.createChannelInlineWrapper}>
            <CreateChannelForm
              workspaceId={selectedWorkspaceId}
              onCreated={handleChannelCreated}
            />
          </div>
        )}

        <div className={styles.sidebarBody}>
          <div className={styles.channelGroupHeader}>
            <span>CHANNELS</span>
            <span className={styles.groupCount}>{channels.length}</span>
          </div>

          {isLoadingChannels && channels.length === 0 ? (
            <div className={styles.channelSkeletonGroup}>
              <div className={styles.channelSkeleton} />
              <div className={styles.channelSkeleton} />
              <div className={styles.channelSkeleton} />
            </div>
          ) : channels.length === 0 ? (
            <div className={styles.noChannelsState}>
              <p>No channels yet.</p>
              <button
                type="button"
                className={styles.firstChannelButton}
                onClick={() => setShowCreateChannel(true)}
              >
                + Create Channel
              </button>
            </div>
          ) : (
            <nav className={styles.channelList}>
              {channels.map((channel) => {
                const isActive = channel.id === selectedChannelId;
                return (
                  <button
                    className={`${styles.channelButton} ${
                      isActive ? styles.activeChannel : ""
                    }`}
                    key={channel.id}
                    type="button"
                    onClick={() => selectChannel(channel.id)}
                    onMouseEnter={() => void prefetchChannel(channel.id)}
                    aria-current={isActive ? "true" : undefined}
                  >
                    <span className={styles.channelHash}>#</span>
                    <span className={styles.channelTitle}>{channel.name}</span>
                  </button>
                );
              })}
            </nav>
          )}
        </div>
      </aside>

      {/* 3. Main Persistent Area (Middle Conversation & Collapsible Right Panel) */}
      <main className={styles.main}>
        {error && <p className={styles.error}>{error}</p>}
        {selectedChannelId ? (
          <ChannelShell
            key={selectedChannelId}
            channelId={selectedChannelId}
            workspaceName={selectedWorkspace?.name}
          />
        ) : (
          <div className={styles.emptyState}>
            <div className={styles.emptyStateCard}>
              <span className={styles.emptyIcon}>🚀</span>
              <h1>Welcome to {selectedWorkspace?.name ?? "Working Space"}</h1>
              <p>
                Select a channel from the sidebar or create a new one to start
                chatting and sharing files.
              </p>
              <button
                type="button"
                className={styles.primaryActionButton}
                onClick={() => setShowCreateChannel(true)}
              >
                + Create Channel
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Create Workspace Modal */}
      {showCreateWorkspace && (
        <div
          className={styles.modalBackdrop}
          onClick={() => setShowCreateWorkspace(false)}
        >
          <div
            className={styles.modal}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className={styles.closeButton}
              type="button"
              onClick={() => setShowCreateWorkspace(false)}
              aria-label="Close dialog"
            >
              ×
            </button>
            <CreateWorkspaceForm onCreated={handleWorkspaceCreated} />
          </div>
        </div>
      )}

      {/* Notification Inbox Popover */}
      <NotificationInbox onSelectChannel={(channelId) => selectChannel(channelId)} />
    </div>
  </NotificationsProvider>
  );
}
