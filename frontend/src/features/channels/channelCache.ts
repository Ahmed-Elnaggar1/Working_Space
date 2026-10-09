import {
  getChannel,
  getChannelFiles,
  getChannelMembers,
  getChannelMessages,
} from "./api";
import { getWorkspaceChannels } from "../workspaces/api";
import type {
  Channel,
  ChannelFile,
  ChannelMember,
  ChannelMessage,
} from "./types";
import type { Workspace } from "../workspaces/types";

export interface ChannelData {
  channel: Channel;
  members: ChannelMember[];
  files: ChannelFile[];
}

export interface MessagesData {
  items: ChannelMessage[];
  nextCursor: string | null;
}

// In-memory cache structures
let workspacesCache: Workspace[] | null = null;
const workspaceChannelsCache = new Map<string, Channel[]>();
const channelDataCache = new Map<string, ChannelData>();
const channelMessagesCache = new Map<string, MessagesData>();
const inflightPrefetches = new Set<string>();

export function getCachedWorkspaces(): Workspace[] | null {
  return workspacesCache;
}

export function setCachedWorkspaces(workspaces: Workspace[]): void {
  workspacesCache = workspaces;
}

export function getCachedWorkspaceChannels(workspaceId: string): Channel[] | undefined {
  return workspaceChannelsCache.get(workspaceId);
}

export function setCachedWorkspaceChannels(workspaceId: string, channels: Channel[]): void {
  workspaceChannelsCache.set(workspaceId, channels);
}

export function addCachedChannel(workspaceId: string, channel: Channel): void {
  const existing = workspaceChannelsCache.get(workspaceId) ?? [];
  if (!existing.some((c) => c.id === channel.id)) {
    workspaceChannelsCache.set(workspaceId, [...existing, channel]);
  }
}

export function addCachedWorkspace(workspace: Workspace): void {
  if (workspacesCache && !workspacesCache.some((w) => w.id === workspace.id)) {
    workspacesCache = [...workspacesCache, workspace];
  }
}

export function getCachedChannelData(channelId: string): ChannelData | undefined {
  return channelDataCache.get(channelId);
}

export function setCachedChannelData(channelId: string, data: ChannelData): void {
  channelDataCache.set(channelId, data);
}

export function updateCachedFiles(channelId: string, files: ChannelFile[]): void {
  const current = channelDataCache.get(channelId);
  if (current) {
    channelDataCache.set(channelId, { ...current, files });
  }
}

export function updateCachedMembers(channelId: string, members: ChannelMember[]): void {
  const current = channelDataCache.get(channelId);
  if (current) {
    channelDataCache.set(channelId, { ...current, members });
  }
}

export function getCachedMessages(channelId: string): MessagesData | undefined {
  return channelMessagesCache.get(channelId);
}

export function setCachedMessages(
  channelId: string,
  items: ChannelMessage[],
  nextCursor: string | null,
): void {
  channelMessagesCache.set(channelId, { items, nextCursor });
}

export function appendCachedMessage(channelId: string, message: ChannelMessage): void {
  const current = channelMessagesCache.get(channelId);
  if (current) {
    if (!current.items.some((m) => m.id === message.id)) {
      channelMessagesCache.set(channelId, {
        ...current,
        items: [...current.items, message],
      });
    }
  }
}

/**
 * Prefetches channel details and recent messages on hover so switching is instant.
 */
export async function prefetchChannel(channelId: string): Promise<void> {
  if (!channelId || inflightPrefetches.has(channelId)) {
    return;
  }

  // If already in cache, no need to prefetch
  if (channelDataCache.has(channelId) && channelMessagesCache.has(channelId)) {
    return;
  }

  inflightPrefetches.add(channelId);

  try {
    const [channel, members, files, messages] = await Promise.all([
      getChannel(channelId),
      getChannelMembers(channelId),
      getChannelFiles(channelId),
      getChannelMessages(channelId),
    ]);

    channelDataCache.set(channelId, { channel, members, files });
    channelMessagesCache.set(channelId, {
      items: messages.items,
      nextCursor: messages.next_cursor,
    });
  } catch {
    // Non-fatal prefetch failure
  } finally {
    inflightPrefetches.delete(channelId);
  }
}

/**
 * Helper to prefetch a workspace's channel list.
 */
export async function prefetchWorkspaceChannels(workspaceId: string): Promise<void> {
  if (!workspaceId || workspaceChannelsCache.has(workspaceId)) {
    return;
  }
  try {
    const channels = await getWorkspaceChannels(workspaceId);
    workspaceChannelsCache.set(workspaceId, channels);
  } catch {
    // Non-fatal
  }
}
