export const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;

const EXTENSIONS = new Set(['pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'webp', 'mp4', 'webm']);
const MIME_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'image/png',
  'image/jpeg',
  'image/webp',
  'video/mp4',
  'video/webm'
]);

export const UNSUPPORTED_MESSAGE = "That file type isn't supported. Try a PDF, DOCX, TXT, image (PNG, JPG, WEBP) or video (MP4, WEBM).";
export const ONE_ATTACHMENT_MESSAGE = 'Only one attachment at a time. Remove the current one to add another.';
export const MANY_FILES_MESSAGE = 'Please add one file at a time.';

export function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function validateAttachmentFiles(files, hasAttachment = false) {
  const list = Array.from(files || []);
  if (list.length > 1) return { error: MANY_FILES_MESSAGE };
  if (list.length === 0) return { error: '' };
  if (hasAttachment) return { error: ONE_ATTACHMENT_MESSAGE };
  const file = list[0];
  if (file.size > MAX_ATTACHMENT_BYTES) {
    return { error: `Only files up to 5 MB are allowed. ${file.name} is ${formatFileSize(file.size)}.` };
  }
  const extension = file.name.split('.').pop()?.toLowerCase() || '';
  if (!EXTENSIONS.has(extension) || (file.type && file.type !== 'application/octet-stream' && !MIME_TYPES.has(file.type))) {
    return { error: UNSUPPORTED_MESSAGE };
  }
  return { file, error: '' };
}
