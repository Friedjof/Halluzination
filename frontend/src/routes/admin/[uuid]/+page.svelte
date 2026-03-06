<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import Sortable from 'sortablejs';

  import { io, type Socket } from 'socket.io-client';

  import { api } from '$lib/api';
  import { adminToken } from '$lib/stores/auth';
  import type { Game, Round } from '$lib/types';

  import RoundCard from '$lib/components/admin/RoundCard.svelte';
  import RoundFormModal from '$lib/components/admin/RoundFormModal.svelte';
  import ConfirmDialog from '$lib/components/admin/ConfirmDialog.svelte';

  $: uuid = $page.params.uuid;

  let game: Game | null = null;
  let loading = true;
  let error = '';

  // Modal state
  let showForm = false;
  let editingRound: Round | null = null;

  // Delete state
  let deletingRound: Round | null = null;
  let deleteAnim: number | null = null;

  type LiveParticipant = { id: number; username: string; score: number; ready: boolean };
  let participants: LiveParticipant[] = [];

  // Sortable
  let listEl: HTMLElement;

  let socketConnected = false;
  let lobbySocket: Socket;

  const BACKEND = import.meta.env.VITE_BACKEND_URL ?? '';

  onMount(async () => {
    if (!$adminToken) { goto('/admin'); return; }
    await loadGame();

    // Fresh socket per page-visit – avoids singleton state issues
    lobbySocket = io(BACKEND);

    lobbySocket.on('connect', () => {
      socketConnected = true;
      lobbySocket.emit('join_admin', { game_uuid: uuid, admin_token: $adminToken });
    });

    lobbySocket.on('disconnect', () => { socketConnected = false; });

    // Single event replaces participant_joined / participant_removed / participant_ready.
    // The server always sends the full list from a socket handler (reliable).
    lobbySocket.on('participants_update', (data: { participants: LiveParticipant[] }) => {
      participants = data.participants;
    });

    lobbySocket.on('game_started', () => {
      window.open(`/present/${uuid}`, `present-${uuid}`);
      goto(`/admin/${uuid}/master`);
    });
  });

  onDestroy(() => {
    lobbySocket?.disconnect();
  });

  function kickParticipant(id: number) {
    lobbySocket?.emit('admin_action', {
      game_uuid: uuid,
      admin_token: $adminToken,
      action: 'kick',
      participant_id: id,
    });
  }

  async function loadGame() {
    loading = true;
    error = '';
    try {
      game = await api.get(`/api/games/${uuid}`);
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  // Called after listEl is rendered in DOM
  function initSortable(node: HTMLElement) {
    const sortable = Sortable.create(node, {
      animation: 150,
      handle: '.drag-handle',
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      onEnd: async (evt) => {
        if (evt.oldIndex === evt.newIndex || !game) return;
        const reordered = [...game.rounds];
        const [moved] = reordered.splice(evt.oldIndex!, 1);
        reordered.splice(evt.newIndex!, 0, moved);

        // Assign new positions
        game = { ...game, rounds: reordered.map((r, i) => ({ ...r, position: i })) };

        // Persist to server
        await Promise.all(
          reordered.map((r, i) => api.patch(`/api/games/${uuid}/rounds/${r.id}`, { position: i }))
        );
      },
    });
    return { destroy: () => sortable.destroy() };
  }

  function openCreate() {
    editingRound = null;
    showForm = true;
  }

  function openEdit(round: Round) {
    editingRound = round;
    showForm = true;
  }

  function onSave(evt: CustomEvent<Round>) {
    showForm = false;
    const saved = evt.detail;
    if (!game) return;
    const idx = game.rounds.findIndex((r) => r.id === saved.id);
    if (idx >= 0) {
      const rounds = [...game.rounds];
      rounds[idx] = saved;
      game = { ...game, rounds };
    } else {
      game = { ...game, rounds: [...game.rounds, saved] };
    }
  }

  function confirmDelete(round: Round) {
    deletingRound = round;
  }

  async function doDelete() {
    if (!deletingRound || !game) return;
    const id = deletingRound.id;
    deletingRound = null;
    try {
      await api.delete(`/api/games/${uuid}/rounds/${id}`);
      game = { ...game, rounds: game.rounds.filter((r) => r.id !== id) };
    } catch (e: any) {
      error = e.message;
    }
  }

  async function copyLink() {
    if (!game) return;
    await navigator.clipboard.writeText(game.join_url);
    copied = true;
    setTimeout(() => (copied = false), 2000);
  }

  let copied = false;
  let exporting = false;
  let exportError = '';

  const BASE = import.meta.env.VITE_BACKEND_URL ?? '';

  async function exportGame() {
    exporting = true;
    exportError = '';
    try {
      const res = await fetch(`${BASE}/api/games/${uuid}/export`, {
        headers: { 'X-Admin-Token': $adminToken },
      });
      if (!res.ok) throw new Error('Export fehlgeschlagen');
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') ?? '';
      const nameMatch = disposition.match(/filename="([^"]+)"/);
      const filename = nameMatch?.[1] ?? `halluzination_${uuid}_export.zip`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      exportError = e.message;
    } finally {
      exporting = false;
    }
  }

  async function startGame() {
    if (!game) return;
    try {
      await api.post(`/api/games/${uuid}/start`);
      game = { ...game, status: 'active' };
      window.open(`/present/${uuid}`, `present-${uuid}`);
      goto(`/admin/${uuid}/master`);
    } catch (e: any) {
      error = e.message;
    }
  }
</script>

{#if loading}
  <p class="loading">Lade Spieldaten…</p>
{:else if error}
  <p class="error-msg">{error}</p>
{:else if game}
  <!-- Top bar -->
  <div class="top-bar">
    <div class="game-info">
      <h1>{game.title}</h1>
      <span class="status status-{game.status}">
        {game.status === 'lobby' ? 'Lobby' : game.status === 'active' ? 'Aktiv' : 'Beendet'}
      </span>
    </div>

    <div class="top-actions">
      <button class="btn-export" on:click={exportGame} disabled={exporting} title="Spiel exportieren (ZIP)">
        {exporting ? '…' : '⬇ Export'}
      </button>
      {#if game.status === 'lobby'}
        <button class="btn-start" on:click={startGame}>▶ Spiel starten</button>
      {:else if game.status === 'active'}
        <button class="btn-resume" on:click={() => { window.open(`/present/${uuid}`, `present-${uuid}`); goto(`/admin/${uuid}/master`); }}>▶ Zum Spielpanel</button>
      {/if}
    </div>
    {#if exportError}<p class="export-error">{exportError}</p>{/if}
  </div>

  <!-- Setup guide -->
  {#if game.status === 'lobby'}
  <div class="guide-card">
    <div class="guide-steps">
      <div class="step">
        <span class="step-num">1</span>
        <span>Runden anlegen und sortieren</span>
      </div>
      <div class="step-sep">→</div>
      <div class="step">
        <span class="step-num">2</span>
        <span>Präsentationsfenster öffnet sich beim Start – QR-Code für Teilnehmer sichtbar</span>
      </div>
      <div class="step-sep">→</div>
      <div class="step">
        <span class="step-num">3</span>
        <span>Spiel starten</span>
      </div>
    </div>
    <div class="guide-link">
      <code class="join-url">{game.join_url}</code>
      <button class="btn-copy" on:click={copyLink}>
        {copied ? '✅ Kopiert!' : '📋 Kopieren'}
      </button>
    </div>
  </div>
  {/if}

  <!-- Participants -->
  <div class="participants-bar">
    <span class="participants-label">
      Teilnehmer ({participants.filter(p => p.ready).length}/{participants.length} bereit)
      {#if socketConnected}<span class="live-dot" title="Live">●</span>{/if}
    </span>
    {#if participants.length === 0}
      <span class="participants-empty">Noch niemand beigetreten</span>
    {:else}
      {#each participants as p (p.id)}
        <span class="participant-chip" class:chip-ready={p.ready}>
          {#if p.ready}<span class="check">✓</span>{/if}
          {p.username}
          <button class="chip-remove" title="Entfernen" on:click={() => kickParticipant(p.id)}>×</button>
        </span>
      {/each}
    {/if}
  </div>

  <!-- Rounds -->
  <div class="rounds-header">
    <h2>Runden ({game.rounds.length})</h2>
    <button class="btn-add" on:click={openCreate}>+ Neue Runde</button>
  </div>

  {#if game.rounds.length === 0}
    <div class="empty">
      <p>Noch keine Runden angelegt.</p>
      <button class="btn-add" on:click={openCreate}>+ Erste Runde hinzufügen</button>
    </div>
  {:else}
    <div class="rounds-list" bind:this={listEl} use:initSortable>
      {#each game.rounds as round, i (round.id)}
        <div class="round-item">
          <RoundCard
            {round}
            index={i}
            on:edit={(e) => openEdit(e.detail)}
            on:delete={(e) => confirmDelete(e.detail)}
          />
        </div>
      {/each}
    </div>
  {/if}
{/if}

<!-- Modals -->
{#if showForm}
  <RoundFormModal
    gameUuid={uuid}
    round={editingRound}
    on:save={onSave}
    on:close={() => (showForm = false)}
  />
{/if}

{#if deletingRound}
  <ConfirmDialog
    message="Runde wirklich löschen? Die Bilder werden vom Server entfernt. Das kann nicht rückgängig gemacht werden."
    confirmLabel="Löschen"
    on:confirm={doDelete}
    on:cancel={() => (deletingRound = null)}
  />
{/if}

<style>
  .loading { color: #888; margin-top: 2rem; text-align: center; }
  .error-msg {
    color: #dc3545;
    background: #fff5f5;
    border: 1px solid #fecaca;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-top: 1rem;
  }

  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.5rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .game-info { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }

  h1 { font-size: 1.4rem; color: #1a1a2e; }

  .status {
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0.25rem 0.65rem;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .status-lobby { background: #fef3cd; color: #856404; }
  .status-active { background: #d1fae5; color: #065f46; }
  .status-finished { background: #f0f2f5; color: #666; }

  .top-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .btn-export {
    background: #f0f2f5;
    color: #444;
    border: 1.5px solid #d0d5dd;
    border-radius: 8px;
    padding: 0.55rem 1rem;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
  }
  .btn-export:hover:not(:disabled) { background: #e0e3e8; }
  .btn-export:disabled { opacity: 0.5; cursor: not-allowed; }

  .export-error {
    font-size: 0.82rem;
    color: #dc3545;
    margin: -0.75rem 0 0;
    text-align: right;
  }

  .btn-start {
    background: #28a745;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.6rem 1.2rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-start:hover { background: #218838; }

  .btn-resume {
    background: #0066cc;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.6rem 1.2rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-resume:hover { background: #0052a3; }

  /* Guide card */
  .guide-card {
    background: white;
    border-radius: 12px;
    padding: 1.1rem 1.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
  }

  .guide-steps {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .step {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: #444;
  }

  .step-num {
    background: #1a1a2e;
    color: white;
    border-radius: 50%;
    width: 1.4rem;
    height: 1.4rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 700;
    flex-shrink: 0;
  }

  .step-sep { color: #ccc; font-size: 0.9rem; }

  .guide-link {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .join-url {
    font-size: 0.85rem;
    color: #0066cc;
    word-break: break-all;
    background: #f0f6ff;
    padding: 0.35rem 0.65rem;
    border-radius: 6px;
    flex: 1;
    min-width: 0;
  }

  .btn-copy {
    background: #f0f2f5;
    border: none;
    border-radius: 6px;
    padding: 0.4rem 0.9rem;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    color: #333;
    white-space: nowrap;
  }
  .btn-copy:hover { background: #e0e3e8; }

  /* Participants bar */
  .participants-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    background: white;
    border-radius: 10px;
    padding: 0.7rem 1rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  }

  .participants-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-right: 0.25rem;
    white-space: nowrap;
  }

  .participants-empty {
    font-size: 0.82rem;
    color: #bbb;
    font-style: italic;
  }

  .live-dot {
    color: #28a745;
    font-size: 0.6rem;
    vertical-align: middle;
    margin-left: 0.25rem;
    animation: pulse-dot 1.5s ease-in-out infinite;
  }
  @keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.3; }
  }

  .participant-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    background: #eef4ff;
    color: #0066cc;
    border-radius: 20px;
    padding: 0.2rem 0.4rem 0.2rem 0.65rem;
    font-size: 0.82rem;
    font-weight: 600;
    animation: pop-in 0.2s ease;
    transition: background 0.3s, color 0.3s;
  }

  .participant-chip.chip-ready {
    background: #d1fae5;
    color: #065f46;
  }

  .check { font-size: 0.75rem; }

  .chip-remove {
    background: none;
    border: none;
    color: #0066cc;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 0 0.1rem;
    opacity: 0.5;
    border-radius: 50%;
    transition: opacity 0.1s, background 0.1s;
  }
  .chip-remove:hover {
    opacity: 1;
    background: rgba(0,102,204,0.15);
  }

  @keyframes pop-in {
    from { transform: scale(0.7); opacity: 0; }
    to   { transform: scale(1);   opacity: 1; }
  }

  /* Rounds */
  .rounds-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }
  h2 { font-size: 1rem; font-weight: 700; color: #1a1a2e; }

  .btn-add {
    background: #1a1a2e;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.55rem 1rem;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-add:hover { opacity: 0.85; }

  .rounds-list {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
  }

  @media (max-width: 1100px) { .rounds-list { grid-template-columns: repeat(3, 1fr); } }
  @media (max-width: 760px)  { .rounds-list { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 480px)  { .rounds-list { grid-template-columns: 1fr; } }

  .empty {
    background: white;
    border-radius: 10px;
    padding: 2.5rem;
    text-align: center;
    color: #888;
    border: 2px dashed #e0e3e8;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }

</style>
