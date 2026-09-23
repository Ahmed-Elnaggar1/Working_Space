import { api } from "../../shared/api";
import type { Channel, ChannelMember } from "./types";

export function getChannel(channelId: string): Promise<Channel> {
  return api.get<Channel>(`/channels/${channelId}`);
}

export function getChannelMembers(channelId: string): Promise<ChannelMember[]> {
  return api.get<ChannelMember[]>(`/channels/${channelId}/members`);
}
