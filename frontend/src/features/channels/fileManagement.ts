import { ApiError } from "../../shared/api";
import type {
  ChannelFile,
  ChannelFileIngestionStatus,
  ChannelMemberRole,
} from "./types";

/**
 * Polling interval for channel file ingestion status updates in milliseconds.
 * Set to 3000ms (3 seconds) per Sprint 7 specification (S7-06).
 */
export const INGESTION_POLL_INTERVAL_MS = 3000;

export type FileAction = "list" | "upload" | "download" | "retry" | "delete";

/**
 * Checks if the user's role allows uploading files to a channel.
 * Per permissions.md: Owner, Admin, and Member can upload; Read-only cannot.
 */
export function canUploadFiles(
  role: ChannelMemberRole | null | undefined,
): boolean {
  return role === "owner" || role === "admin" || role === "member";
}

/**
 * Checks if the user's role allows deleting a specific file.
 * Per permissions.md:
 * - Owner and Admin can delete any file.
 * - Member can delete only their own files (where fileUploadedBy matches currentUserId).
 * - Read-only cannot delete any files.
 */
export function canDeleteFile(
  role: ChannelMemberRole | null | undefined,
  fileUploadedBy: string,
  currentUserId: string | null | undefined,
): boolean {
  if (role === "owner" || role === "admin") {
    return true;
  }
  if (role === "member") {
    return Boolean(currentUserId && fileUploadedBy === currentUserId);
  }
  return false;
}

/**
 * Checks if retry ingestion action is applicable.
 * S7-07: Retry action appears only on failed files, and requires upload_files permission.
 */
export function canRetryIngestion(
  role: ChannelMemberRole | null | undefined,
  status: ChannelFileIngestionStatus,
): boolean {
  if (status !== "failed") {
    return false;
  }
  return canUploadFiles(role);
}

/**
 * Checks whether any file in the list has an active (non-terminal) ingestion status.
 */
export function hasActiveIngestion(files: ChannelFile[]): boolean {
  return files.some(
    (file) =>
      file.ingestion_status === "pending" ||
      file.ingestion_status === "processing",
  );
}

/**
 * Maps API errors to user-friendly messages for file actions.
 */
export function getFileActionErrorMessage(
  action: FileAction,
  error: unknown,
): string {
  if (!(error instanceof ApiError)) {
    return getFallbackMessage(action);
  }

  if (error.status === 403) {
    return getForbiddenMessage(action);
  }

  if (error.status === 404) {
    if (action === "delete" || action === "download" || action === "retry") {
      return "File not found.";
    }
    if (action === "list" || action === "upload") {
      return "Channel not found.";
    }
  }

  if (error.status === 400) {
    if (action === "retry") {
      return "Completed file ingestions cannot be retried.";
    }
    if (action === "upload") {
      return (
        error.message ||
        "Unsupported file type. Only PDF (.pdf) and plain text (.txt) files are supported."
      );
    }
  }

  return error.message;
}

function getForbiddenMessage(action: FileAction): string {
  switch (action) {
    case "upload":
      return "You do not have permission to upload files to this channel.";
    case "delete":
      return "You do not have permission to delete this file.";
    case "retry":
      return "You do not have permission to retry ingestion for this file.";
    case "download":
      return "You do not have permission to download files from this channel.";
    case "list":
    default:
      return "You do not have permission to view files in this channel.";
  }
}

function getFallbackMessage(action: FileAction): string {
  switch (action) {
    case "upload":
      return "Unable to upload file. Please try again.";
    case "delete":
      return "Unable to delete file. Please try again.";
    case "retry":
      return "Unable to retry ingestion. Please try again.";
    case "download":
      return "Unable to download file. Please try again.";
    case "list":
    default:
      return "Unable to load channel files. Please try again.";
  }
}
