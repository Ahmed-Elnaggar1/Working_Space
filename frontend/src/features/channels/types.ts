export interface Channel {
  id: string;
  workspace_id: string;
  name: string;
  created_at: string;
}

export type ChannelMemberRole = "owner" | "admin" | "member" | "read_only";

export interface ChannelMember {
  id: string;
  user_id: string;
  email: string;
  channel_id: string;
  role: ChannelMemberRole;
}

export interface AddChannelMemberInput {
  email: string;
  role: ChannelMemberRole;
}

export interface MembershipResponse {
  id: string;
  user_id: string;
  channel_id: string;
  role: ChannelMemberRole;
}
