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

export interface UpdateChannelMemberInput {
  role: ChannelMemberRole;
}

export type ChannelFileIngestionStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed";

export interface ChannelFile {
  id: string;
  channel_id: string;
  filename: string;
  file_name?: string;
  storage_path: string;
  uploaded_by: string;
  ingestion_status: ChannelFileIngestionStatus;
  ingestion_error?: string | null;
  created_at: string;
}

export interface BotCitation {
  file_id: string;
  file_name: string;
  page: number | null;
}

export interface AskChannelRequest {
  question: string;
}

export interface AskChannelResponse {
  answer: string;
  citations: BotCitation[];
  insufficient_evidence: boolean;
}

export type BotQAPairStatus =
  | "loading"
  | "success"
  | "insufficient_evidence"
  | "error";

export interface BotQAPair {
  id: string;
  question: string;
  answer?: string;
  citations?: BotCitation[];
  insufficient_evidence?: boolean;
  status: BotQAPairStatus;
  errorMessage?: string;
  isRetryable?: boolean;
  createdAt: string;
}
