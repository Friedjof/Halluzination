<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Round } from '$lib/types';

  export let round: Round;
  export let index: number;

  const dispatch = createEventDispatcher<{ edit: Round; delete: Round }>();

  $: correctLocation = round.locations.find((l) => l.is_correct);
  $: shortText =
    round.solution_text.length > 48
      ? round.solution_text.slice(0, 48) + '…'
      : round.solution_text;

  const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
  $: imageUrl = round.original_url
    ? round.original_url.startsWith('http')
      ? round.original_url
      : `${BACKEND}${round.original_url}`
    : null;
</script>

<div class="card" data-id={round.id}>
  <!-- Drag handle – top-left corner -->
  <div class="drag-handle" title="Verschieben">⠿</div>

  <!-- Image – fixed 16:9 area, object-fit: cover -->
  <div class="preview">
    {#if imageUrl}
      <img src={imageUrl} alt="Runde {index + 1}" />
    {:else}
      <div class="no-image">🖼️</div>
    {/if}
  </div>

  <!-- Info -->
  <div class="info">
    <span class="number">Runde {index + 1}</span>
    <p class="text" title={round.solution_text}>{shortText || '–'}</p>
    <div class="badges">
      {#if correctLocation}
        <span class="badge location">📍 {correctLocation.name}</span>
      {/if}
      {#if round.target_year}
        <span class="badge year">📅 {round.target_year}</span>
      {/if}
      <span class="badge time">⏱ {round.time_limit}s</span>
    </div>
  </div>

  <!-- Actions -->
  <div class="actions">
    <button class="btn-icon" title="Bearbeiten" on:click={() => dispatch('edit', round)}>✏️</button>
    <button class="btn-icon danger" title="Löschen" on:click={() => dispatch('delete', round)}>🗑</button>
  </div>
</div>

<style>
  .card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: box-shadow 0.15s;
    position: relative;
  }
  .card:hover { box-shadow: 0 6px 20px rgba(0,0,0,0.13); }

  :global(.sortable-ghost) { opacity: 0.35; }
  :global(.sortable-chosen) { box-shadow: 0 10px 28px rgba(0,0,0,0.2) !important; }

  /* Drag handle – absolute top-left so it doesn't affect layout */
  .drag-handle {
    position: absolute;
    top: 0.4rem;
    left: 0.4rem;
    z-index: 2;
    color: white;
    cursor: grab;
    font-size: 1.1rem;
    user-select: none;
    text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    padding: 0.1rem 0.2rem;
  }
  .drag-handle:active { cursor: grabbing; }

  /* Image area: fixed 16:9 ratio, always the same size */
  .preview {
    width: 100%;
    aspect-ratio: 16 / 9;
    background: #1a1a2e;
    overflow: hidden;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .no-image { font-size: 2.5rem; opacity: 0.25; }

  /* Info section */
  .info {
    padding: 0.7rem 0.85rem 0.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    flex: 1;
  }

  .number {
    font-size: 0.68rem;
    font-weight: 700;
    color: #0066cc;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .text {
    font-size: 0.82rem;
    color: #333;
    line-height: 1.35;
    /* Exactly 2 lines, then ellipsis */
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 2.2em;
  }

  .badges {
    display: flex;
    gap: 0.3rem;
    flex-wrap: wrap;
    margin-top: 0.2rem;
  }
  .badge {
    font-size: 0.68rem;
    padding: 0.15rem 0.45rem;
    border-radius: 20px;
    white-space: nowrap;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .location { background: #e8f4fd; color: #0066cc; }
  .year     { background: #fef3cd; color: #856404; }
  .time     { background: #f0f2f5; color: #555; }

  /* Action buttons – always pinned to bottom */
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.35rem;
    padding: 0.5rem 0.75rem 0.65rem;
    border-top: 1px solid #f0f2f5;
  }

  .btn-icon {
    background: none;
    border: 1px solid #e0e3e8;
    border-radius: 6px;
    padding: 0.25rem 0.5rem;
    cursor: pointer;
    font-size: 0.95rem;
    line-height: 1;
    transition: background 0.12s;
  }
  .btn-icon:hover { background: #f0f2f5; }
  .btn-icon.danger:hover { background: #fff5f5; border-color: #fecaca; }
</style>
