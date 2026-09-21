import { api } from "../../shared/api";
import type { Workspace, WorkspaceCreateInput } from "./types";

export function createWorkspace(
  input: WorkspaceCreateInput,
): Promise<Workspace> {
  return api.post<Workspace>("/workspaces", input);
}

export function getWorkspaces(): Promise<Workspace[]> {
  return api.get<Workspace[]>("/workspaces");
}
