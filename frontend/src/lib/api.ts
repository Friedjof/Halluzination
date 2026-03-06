import { get } from 'svelte/store';
import { adminToken } from '$lib/stores/auth';

const BASE_URL = import.meta.env.VITE_BACKEND_URL ?? '';

async function request(method: string, path: string, body?: unknown) {
  const token = get(adminToken);
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': token,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Anfrage fehlgeschlagen');
  }
  if (res.status === 204) return null;
  return res.json();
}

/** Upload images with XHR to track progress. Returns a promise with progress updates. */
export function uploadImages(
  gameUuid: string,
  roundId: number,
  original: File | null,
  ai: File | null,
  onProgress: (pct: number) => void
): Promise<{ original_url: string; ai_url: string }> {
  return new Promise((resolve, reject) => {
    const token = get(adminToken);
    const formData = new FormData();
    if (original) formData.append('original', original);
    if (ai) formData.append('ai', ai);

    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        const body = JSON.parse(xhr.responseText ?? '{}');
        reject(new Error(body.detail ?? 'Upload fehlgeschlagen'));
      }
    };
    xhr.onerror = () => reject(new Error('Upload fehlgeschlagen'));
    xhr.open('POST', `${BASE_URL}/api/games/${gameUuid}/rounds/${roundId}/upload`);
    xhr.setRequestHeader('X-Admin-Token', token);
    xhr.send(formData);
  });
}

export const api = {
  get: (path: string) => request('GET', path),
  post: (path: string, body?: unknown) => request('POST', path, body),
  patch: (path: string, body?: unknown) => request('PATCH', path, body),
  delete: (path: string) => request('DELETE', path),
};
