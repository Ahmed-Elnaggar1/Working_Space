import { api } from "../../shared/api";
import type {
  AddChannelMemberInput,
  Channel,
  ChannelMember,
  MembershipResponse,
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
