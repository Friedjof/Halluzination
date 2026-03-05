<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let message: string;
  export let confirmLabel = 'Löschen';

  const dispatch = createEventDispatcher<{ confirm: void; cancel: void }>();
</script>

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div class="backdrop" role="dialog" aria-modal="true" on:click|self={() => dispatch('cancel')}>
  <div class="dialog">
    <p>{message}</p>
    <div class="actions">
      <button class="cancel" on:click={() => dispatch('cancel')}>Abbrechen</button>
      <button class="confirm" on:click={() => dispatch('confirm')}>{confirmLabel}</button>
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 500;
    backdrop-filter: blur(2px);
  }

  .dialog {
    background: white;
    border-radius: 12px;
    padding: 1.75rem 2rem;
    max-width: 380px;
    width: 90%;
    box-shadow: 0 12px 40px rgba(0,0,0,0.2);
  }

  p {
    font-size: 0.95rem;
    line-height: 1.5;
    color: #333;
    margin-bottom: 1.5rem;
  }

  .actions { display: flex; gap: 0.75rem; justify-content: flex-end; }

  button {
    padding: 0.55rem 1.2rem;
    border-radius: 8px;
    border: none;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
  }
  .cancel { background: #f0f2f5; color: #333; }
  .cancel:hover { background: #e0e3e8; }
  .confirm { background: #dc3545; color: white; }
  .confirm:hover { background: #b02a37; }
</style>
