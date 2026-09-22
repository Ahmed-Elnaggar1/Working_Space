import { api } from "../../shared/api";
import type { Channel } from "./types";

export function getChannel(channelId: string): Promise<Channel> {
  return api.get<Channel>(`/channels/${channelId}`);
}
