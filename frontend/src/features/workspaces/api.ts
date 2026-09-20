import { api } from "../../shared/api";
import type { Workspace } from "./types";

export function getWorkspaces(): Promise<Workspace[]> {
  return api.get<Workspace[]>("/workspaces");
}
