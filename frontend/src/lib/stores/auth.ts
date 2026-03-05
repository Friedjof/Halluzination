import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const stored = browser ? (localStorage.getItem('admin_token') ?? '') : '';
export const adminToken = writable<string>(stored);

if (browser) {
  adminToken.subscribe((value) => {
    localStorage.setItem('admin_token', value);
  });
}
