import {
  api,
  getBaseUrl,
  getTokenProvider,
  parseApiError,
} from "../../shared/api";
import type {
  AddChannelMemberInput,
  Channel,
  ChannelFile,
  ChannelMember,
  ChannelMessage,
  ChannelMessagePage,
  CreateChannelMessageInput,
  MembershipResponse,
  UpdateChannelMemberInput,
} from "./types";

export function getChannel(channelId: string): Promise<Channel> {
  return api.get<Channel>(`/channels/${channelId}`);
}

export function getChannelMembers(channelId: string): Promise<ChannelMember[]> {
  return api.get<ChannelMember[]>(`/channels/${channelId}/members`);
}

export function addChannelMember(
  channelId: string,
  input: AddChannelMemberInput,
): Promise<MembershipResponse> {
  return api.post<MembershipResponse>(`/channels/${channelId}/members`, input);
}

export function updateChannelMemberRole(
  channelId: string,
  userId: string,
  input: UpdateChannelMemberInput,
): Promise<MembershipResponse> {
  return api.patch<MembershipResponse>(
    `/channels/${channelId}/members/${userId}`,
    input,
  );
}

export function removeChannelMember(
  channelId: string,
  userId: string,
): Promise<null> {
  return api.delete<null>(`/channels/${channelId}/members/${userId}`);
}

export function getChannelFiles(channelId: string): Promise<ChannelFile[]> {
  return api.get<ChannelFile[]>(`/channels/${channelId}/files`);
}

export function getChannelWebSocketUrl(
  channelId: string,
  token: string,
  baseUrl: string = getBaseUrl(),
): string {
  const normalizedBase = baseUrl.replace(/\/+$/, "");
  const protocol = normalizedBase.startsWith("https://") ? "wss" : "ws";
  const target = normalizedBase.replace(/^https?:\/\//, "");
  return `${protocol}://${target}/ws/channels/${channelId}?token=${encodeURIComponent(token)}`;
}

export function getChannelMessages(
  channelId: string,
  before?: string,
): Promise<ChannelMessagePage> {
  return api.get<ChannelMessagePage>(`/channels/${channelId}/messages`, {
    params: { limit: 50, before },
  });
}

export function postChannelMessage(
  channelId: string,
  input: CreateChannelMessageInput,
): Promise<ChannelMessage> {
  return api.post<ChannelMessage>(`/channels/${channelId}/messages`, input);
}

export function uploadChannelFile(
  channelId: string,
  file: File,
): Promise<ChannelFile> {
  const formData = new FormData();
  formData.append("file", file);
  return api.post<ChannelFile>(`/channels/${channelId}/files`, formData);
}

export async function downloadChannelFile(
  channelId: string,
  fileId: string,
  filename: string,
): Promise<void> {
  const baseUrl = getBaseUrl();
  const tokenProvider = getTokenProvider();
  const token = tokenProvider ? tokenProvider() : null;
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(
    `${baseUrl}/channels/${channelId}/files/${fileId}/download`,
    {
      method: "GET",
      headers,
      credentials: "include",
    },
  );

  if (!response.ok) {
    throw await parseApiError(response);
  }

  const blob = await response.blob();
  if (typeof window !== "undefined" && typeof document !== "undefined") {
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(objectUrl);
  }
}

export function retryFileIngestion(
  channelId: string,
  fileId: string,
): Promise<ChannelFile> {
  return api.post<ChannelFile>(
    `/channels/${channelId}/files/${fileId}/retry-ingestion`,
  );
}

export function deleteChannelFile(
  channelId: string,
  fileId: string,
): Promise<null> {
  return api.delete<null>(`/channels/${channelId}/files/${fileId}`);
}
