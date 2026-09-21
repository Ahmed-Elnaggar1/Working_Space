import { api } from "../../shared/api";
import type { Channel, Workspace, WorkspaceCreateInput } from "./types";

export function createWorkspace(
  input: WorkspaceCreateInput,
): Promise<Workspace> {
  return api.post<Workspace>("/workspaces", input);
}

export function getWorkspaces(): Promise<Workspace[]> {
  return api.get<Workspace[]>("/workspaces");
}

export function getWorkspace(workspaceId: string): Promise<Workspace> {
  return api.get<Workspace>(`/workspaces/${workspaceId}`);
}

export function getWorkspaceChannels(workspaceId: string): Promise<Channel[]> {
  return api.get<Channel[]>(`/workspaces/${workspaceId}/channels`);
}
