export interface Workspace {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
}

export interface WorkspaceCreateInput {
  name: string;
}

export interface Channel {
  id: string;
  workspace_id: string;
  name: string;
  created_at: string;
}
