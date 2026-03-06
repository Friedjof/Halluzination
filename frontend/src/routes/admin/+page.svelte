<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { adminToken } from '$lib/stores/auth';

  const BASE = import.meta.env.VITE_BACKEND_URL ?? '';

  let tokenInput = '';
  let gameTitle = '';
  let error = '';
  let loading = false;

  let importFile: File | null = null;
  let importing = false;
  let importError = '';

  async function importGame() {
    if (!importFile) return;
    importing = true;
    importError = '';
    try {
      const fd = new FormData();
      fd.append('file', importFile);
      const res = await fetch(`${BASE}/api/games/import`, {
        method: 'POST',
        headers: { 'X-Admin-Token': $adminToken },
        body: fd,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Import fehlgeschlagen' }));
        throw new Error(body.detail ?? 'Import fehlgeschlagen');
      }
      const data = await res.json();
      goto(`/admin/${data.uuid}`);
    } catch (e: any) {
      importError = e.message;
    } finally {
      importing = false;
    }
  }

  async function login() {
    error = '';
    loading = true;
    try {
      const r = await fetch(`${import.meta.env.VITE_BACKEND_URL ?? ''}/api/auth/verify`, {
        method: 'POST',
        headers: { 'X-Admin-Token': tokenInput },
      });
      if (!r.ok) throw new Error('Ungültiges Token');
      $adminToken = tokenInput;
      tokenInput = '';
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function createGame() {
    if (!gameTitle.trim()) return;
    error = '';
    loading = true;
    try {
      const game = await api.post('/api/games', { title: gameTitle.trim() });
      goto(`/admin/${game.uuid}`);
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="center">
  {#if !$adminToken}
    <div class="card">
      <h1>Admin Login</h1>
      <form on:submit|preventDefault={login}>
        <label>
          Admin-Token
          <input
            type="password"
            bind:value={tokenInput}
            placeholder="Token eingeben…"
            autocomplete="current-password"
            required
          />
        </label>
        {#if error}<p class="error">{error}</p>{/if}
        <button type="submit" disabled={loading || !tokenInput}>
          {loading ? 'Prüfe…' : 'Anmelden'}
        </button>
      </form>
    </div>
  {:else}
    <div class="card">
      <h1>Neues Spiel erstellen</h1>
      <form on:submit|preventDefault={createGame}>
        <label>
          Titel des Spielabends
          <input
            type="text"
            bind:value={gameTitle}
            placeholder="z.B. Spielabend bei Familie Müller"
            required
          />
        </label>
        {#if error}<p class="error">{error}</p>{/if}
        <button type="submit" disabled={loading || !gameTitle.trim()}>
          {loading ? 'Erstelle…' : 'Spiel erstellen →'}
        </button>
      </form>

      <div class="divider"><span>oder</span></div>

      <div class="import-area">
        <p class="import-label">Spiel importieren</p>
        <label class="import-file-label">
          <input
            type="file"
            accept=".zip"
            on:change={(e) => importFile = (e.target as HTMLInputElement).files?.[0] ?? null}
            hidden
          />
          <span class="import-file-btn">
            {importFile ? importFile.name : '📦 ZIP-Datei auswählen…'}
          </span>
        </label>
        {#if importError}<p class="error">{importError}</p>{/if}
        <button
          class="btn-import"
          disabled={importing || !importFile}
          on:click={importGame}
        >
          {importing ? 'Importiere…' : '⬆ Importieren'}
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .center {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 60vh;
  }

  .card {
    background: white;
    border-radius: 12px;
    padding: 2.5rem;
    width: 100%;
    max-width: 420px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
  }

  h1 {
    font-size: 1.4rem;
    margin-bottom: 1.5rem;
    color: #1a1a2e;
  }

  form { display: flex; flex-direction: column; gap: 1rem; }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: #444;
  }

  input {
    border: 1.5px solid #d0d5dd;
    border-radius: 8px;
    padding: 0.65rem 0.9rem;
    font-size: 1rem;
    transition: border-color 0.15s;
  }
  input:focus { outline: none; border-color: #0066cc; }

  button {
    background: #1a1a2e;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.75rem;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
    margin-top: 0.5rem;
  }
  button:disabled { opacity: 0.45; cursor: not-allowed; }
  button:not(:disabled):hover { opacity: 0.85; }

  .divider {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 1.25rem 0 0;
    color: #bbb;
    font-size: 0.82rem;
  }
  .divider::before, .divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #e5e7eb;
  }

  .import-area {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin-top: 1rem;
  }

  .import-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #444;
    margin: 0;
  }

  .import-file-label { cursor: pointer; }

  .import-file-btn {
    display: block;
    border: 1.5px dashed #d0d5dd;
    border-radius: 8px;
    padding: 0.65rem 0.9rem;
    font-size: 0.88rem;
    color: #666;
    transition: border-color 0.15s, background 0.15s;
    word-break: break-all;
  }
  .import-file-label:hover .import-file-btn {
    border-color: #0066cc;
    background: #f0f6ff;
    color: #0066cc;
  }

  .btn-import {
    background: #1a1a2e;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.7rem;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .btn-import:disabled { opacity: 0.45; cursor: not-allowed; }
  .btn-import:not(:disabled):hover { opacity: 0.85; }

  .error {
    color: #dc3545;
    font-size: 0.85rem;
    background: #fff5f5;
    border: 1px solid #fecaca;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
  }
</style>
