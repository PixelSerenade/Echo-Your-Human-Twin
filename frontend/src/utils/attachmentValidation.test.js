import assert from 'node:assert';
import {
  MAX_ATTACHMENT_BYTES,
  UNSUPPORTED_MESSAGE,
  ONE_ATTACHMENT_MESSAGE,
  MANY_FILES_MESSAGE,
  formatFileSize,
  validateAttachmentFiles
} from './attachmentValidation.js';

console.log('Testing attachmentValidation.js...');

// 1. Format file size
assert.strictEqual(formatFileSize(500 * 1024), '500 KB');
assert.strictEqual(formatFileSize(5 * 1024 * 1024), '5.0 MB');
assert.strictEqual(formatFileSize(5.2 * 1024 * 1024), '5.2 MB');

// 2. Size limit: Under 5 MB is accepted
const underDoc = { name: 'notes.pdf', size: 4.9 * 1024 * 1024, type: 'application/pdf' };
const underImg = { name: 'photo.png', size: 4.8 * 1024 * 1024, type: 'image/png' };
const underVid = { name: 'clip.mp4', size: 4.95 * 1024 * 1024, type: 'video/mp4' };

assert.strictEqual(validateAttachmentFiles([underDoc], false).error, '');
assert.strictEqual(validateAttachmentFiles([underImg], false).error, '');
assert.strictEqual(validateAttachmentFiles([underVid], false).error, '');

// 3. Size limit: Just over 5 MB is rejected with friendly message including name and size
const overDoc = { name: 'thesis.pdf', size: 5.1 * 1024 * 1024, type: 'application/pdf' };
const overImg = { name: 'render.png', size: 5.5 * 1024 * 1024, type: 'image/png' };
const overVid = { name: 'movie.mp4', size: 6.2 * 1024 * 1024, type: 'video/mp4' };

const resDoc = validateAttachmentFiles([overDoc], false);
assert(resDoc.error.startsWith('Only files up to 5 MB are allowed.'));
assert(resDoc.error.includes('thesis.pdf'));
assert(resDoc.error.includes('5.1 MB'));

const resImg = validateAttachmentFiles([overImg], false);
assert(resImg.error.startsWith('Only files up to 5 MB are allowed.'));
assert(resImg.error.includes('render.png'));
assert(resImg.error.includes('5.5 MB'));

const resVid = validateAttachmentFiles([overVid], false);
assert(resVid.error.startsWith('Only files up to 5 MB are allowed.'));
assert(resVid.error.includes('movie.mp4'));
assert(resVid.error.includes('6.2 MB'));

// 4. One attachment at a time: Adding second file when one is attached
const secondFile = { name: 'another.pdf', size: 1024, type: 'application/pdf' };
const resSecond = validateAttachmentFiles([secondFile], true);
assert.strictEqual(resSecond.error, ONE_ATTACHMENT_MESSAGE);
assert.strictEqual(resSecond.error, 'Only one attachment at a time. Remove the current one to add another.');

// 5. Dropping or selecting several files at once
const multiFiles = [
  { name: 'doc1.pdf', size: 1024, type: 'application/pdf' },
  { name: 'doc2.pdf', size: 1024, type: 'application/pdf' }
];
const resMulti = validateAttachmentFiles(multiFiles, false);
assert.strictEqual(resMulti.error, MANY_FILES_MESSAGE);
assert.strictEqual(resMulti.error, 'Please add one file at a time.');

// 6. Unsupported types
const unsupportedTypes = [
  { name: 'app.exe', size: 1024, type: 'application/x-msdownload' },
  { name: 'archive.zip', size: 1024, type: 'application/zip' },
  { name: 'song.mp3', size: 1024, type: 'audio/mpeg' },
  { name: 'script.js', size: 1024, type: 'text/javascript' }
];

for (const bad of unsupportedTypes) {
  const resBad = validateAttachmentFiles([bad], false);
  assert.strictEqual(resBad.error, UNSUPPORTED_MESSAGE);
}

// 7. Supported types: PDF, DOCX, TXT, PNG, JPG, WEBP, MP4, WEBM
const supportedTypes = [
  { name: 'doc.pdf', size: 1024, type: 'application/pdf' },
  { name: 'doc.docx', size: 1024, type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
  { name: 'notes.txt', size: 1024, type: 'text/plain' },
  { name: 'pic.png', size: 1024, type: 'image/png' },
  { name: 'pic.jpg', size: 1024, type: 'image/jpeg' },
  { name: 'pic.webp', size: 1024, type: 'image/webp' },
  { name: 'vid.mp4', size: 1024, type: 'video/mp4' },
  { name: 'vid.webm', size: 1024, type: 'video/webm' }
];

for (const good of supportedTypes) {
  const resGood = validateAttachmentFiles([good], false);
  assert.strictEqual(resGood.error, '', `Expected ${good.name} to be valid`);
  assert.strictEqual(resGood.file.name, good.name);
}

console.log('ALL attachmentValidation.js tests passed successfully! PASS');
