import { useState } from "react";
import { deleteChannelFile, downloadChannelFile, retryFileIngestion } from "../api";
import {
  canDeleteFile,
  canRetryIngestion,
  getFileActionErrorMessage,
} from "../fileManagement";
import type {
  ChannelFile,
  ChannelFileIngestionStatus,
  ChannelMember,
  ChannelMemberRole,
} from "../types";
import styles from "./FileList.module.css";

interface FileListProps {
  channelId: string;
  files: ChannelFile[];
  members: ChannelMember[];
  currentUserId: string | undefined;
  currentUserRole: ChannelMemberRole | null | undefined;
  onFileDeleted: (fileId: string) => void;
  onFileUpdated: (file: ChannelFile) => void;
}

export function FileList({
  channelId,
  files,
  members,
  currentUserId,
  currentUserRole,
  onFileDeleted,
  onFileUpdated,
}: FileListProps) {
  const [downloadingFileId, setDownloadingFileId] = useState<string | null>(null);
  const [retryingFileId, setRetryingFileId] = useState<string | null>(null);
  const [deletingFileId, setDeletingFileId] = useState<string | null>(null);
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});

  function setFileError(fileId: string, message: string | null) {
    setActionErrors((prev) => {
      if (message === null) {
        const next = { ...prev };
        delete next[fileId];
        return next;
      }
      return { ...prev, [fileId]: message };
    });
  }

  async function handleDownload(file: ChannelFile) {
    setFileError(file.id, null);
    setDownloadingFileId(file.id);

    try {
      await downloadChannelFile(channelId, file.id, file.filename);
    } catch (err) {
      setFileError(file.id, getFileActionErrorMessage("download", err));
    } finally {
      setDownloadingFileId(null);
    }
  }

  async function handleRetry(file: ChannelFile) {
    setFileError(file.id, null);
    setRetryingFileId(file.id);

    try {
      const updatedFile = await retryFileIngestion(channelId, file.id);
      onFileUpdated(updatedFile);
    } catch (err) {
      setFileError(file.id, getFileActionErrorMessage("retry", err));
    } finally {
      setRetryingFileId(null);
    }
  }

  async function handleDelete(file: ChannelFile) {
    if (!window.confirm(`Delete "${file.filename}"? This action cannot be undone.`)) {
      return;
    }

    setFileError(file.id, null);
    setDeletingFileId(file.id);

    try {
      await deleteChannelFile(channelId, file.id);
      onFileDeleted(file.id);
    } catch (err) {
      setFileError(file.id, getFileActionErrorMessage("delete", err));
    } finally {
      setDeletingFileId(null);
    }
  }

  function renderStatusBadge(status: ChannelFileIngestionStatus) {
    switch (status) {
      case "pending":
        return (
          <span className={`${styles.badge} ${styles.badgePending}`}>
            <span className={styles.badgeDot} />
            Pending
          </span>
        );
      case "processing":
        return (
          <span className={`${styles.badge} ${styles.badgeProcessing}`}>
            <span className={styles.badgeDot} />
            Processing
          </span>
        );
      case "completed":
        return (
          <span className={`${styles.badge} ${styles.badgeCompleted}`}>
            <span className={styles.badgeDot} />
            Completed
          </span>
        );
      case "failed":
        return (
          <span className={`${styles.badge} ${styles.badgeFailed}`}>
            <span className={styles.badgeDot} />
            Failed
          </span>
        );
      default:
        return null;
    }
  }

  function getUploaderDisplay(uploadedBy: string): string {
    const member = members.find((m) => m.user_id === uploadedBy);
    const isCurrentUser = currentUserId && uploadedBy === currentUserId;

    if (member) {
      return isCurrentUser ? `${member.email} (You)` : member.email;
    }

    return isCurrentUser ? `${uploadedBy} (You)` : uploadedBy;
  }

  if (files.length === 0) {
    return <p className={styles.emptyState}>No files uploaded to this channel yet.</p>;
  }

  return (
    <ul className={styles.fileList}>
      {files.map((file) => {
        const canDelete = canDeleteFile(currentUserRole, file.uploaded_by, currentUserId);
        const canRetry = canRetryIngestion(currentUserRole, file.ingestion_status);
        const isDownloading = downloadingFileId === file.id;
        const isRetrying = retryingFileId === file.id;
        const isDeleting = deletingFileId === file.id;
        const isBusy = isDownloading || isRetrying || isDeleting;
        const fileError = actionErrors[file.id];

        return (
          <li key={file.id} className={styles.fileItem}>
            <div className={styles.fileMeta}>
              <div className={styles.fileNameRow}>
                <span className={styles.fileName}>{file.filename}</span>
                {renderStatusBadge(file.ingestion_status)}
              </div>
              <p className={styles.uploaderInfo}>
                Uploaded by <span className={styles.uploaderTag}>{getUploaderDisplay(file.uploaded_by)}</span>
              </p>
              {file.ingestion_status === "failed" && file.ingestion_error && (
                <p className={styles.ingestionError}>Error: {file.ingestion_error}</p>
              )}
              {fileError && <p className={styles.actionError}>{fileError}</p>}
            </div>

            <div className={styles.fileActions}>
              <button
                className={styles.downloadButton}
                type="button"
                disabled={isBusy}
                onClick={() => void handleDownload(file)}
                aria-label={`Download ${file.filename}`}
              >
                {isDownloading ? "Downloading..." : "Download"}
              </button>

              {canRetry && (
                <button
                  className={styles.retryButton}
                  type="button"
                  disabled={isBusy}
                  onClick={() => void handleRetry(file)}
                  aria-label={`Retry ingestion for ${file.filename}`}
                >
                  {isRetrying ? "Retrying..." : "Retry"}
                </button>
              )}

              {canDelete && (
                <button
                  className={styles.deleteButton}
                  type="button"
                  disabled={isBusy}
                  onClick={() => void handleDelete(file)}
                  aria-label={`Delete ${file.filename}`}
                >
                  {isDeleting ? "Deleting..." : "Delete"}
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
