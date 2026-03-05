<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { adminToken } from '$lib/stores/auth';

  let tokenInput = '';
  let gameTitle = '';
  let error = '';
  let loading = false;

  async function login() {
    error = '';
    loading = true;
    try {
      const r = await fetch(`${import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'}/api/auth/verify`, {
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

  .error {
    color: #dc3545;
    font-size: 0.85rem;
    background: #fff5f5;
    border: 1px solid #fecaca;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
  }
</style>
