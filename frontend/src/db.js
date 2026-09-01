import Dexie from 'dexie';

export const db = new Dexie('AudiobookDB');

db.version(1).stores({
  documents: '++id, title, status, createdAt, updatedAt', // Primary key and indexed props
  audio_chunks: '++id, documentId, sectionIndex',
});
