<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let label: string;
  export let preview: string = '';
  export let error: string = '';

  const dispatch = createEventDispatcher<{ select: File }>();

  const ALLOWED = ['image/jpeg', 'image/png', 'image/webp'];
  const MAX_BYTES = 10 * 1024 * 1024;

  let isDragging = false;
  let inputEl: HTMLInputElement;

  function handleFile(file: File | null | undefined) {
    if (!file) return;
    if (!ALLOWED.includes(file.type)) {
      error = 'Nicht erlaubtes Format. Nur JPG, PNG oder WEBP.';
      return;
    }
    if (file.size > MAX_BYTES) {
      error = 'Datei zu groß. Maximal 10 MB erlaubt.';
      return;
    }
    error = '';
    const reader = new FileReader();
    reader.onload = (e) => (preview = e.target?.result as string);
    reader.readAsDataURL(file);
    dispatch('select', file);
  }
</script>

<div class="field-wrapper">
  <span class="field-label">{label} <span class="required">*</span></span>

  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="drop-zone"
    class:dragging={isDragging}
    class:has-preview={!!preview}
    on:dragover|preventDefault={() => (isDragging = true)}
    on:dragleave={() => (isDragging = false)}
    on:drop|preventDefault={(e) => { isDragging = false; handleFile(e.dataTransfer?.files[0]); }}
    on:click={() => inputEl.click()}
    on:keydown={(e) => e.key === 'Enter' && inputEl.click()}
    role="button"
    tabindex="0"
    aria-label="{label} hochladen"
  >
    <input
      bind:this={inputEl}
      type="file"
      accept="image/jpeg,image/png,image/webp"
      on:change={(e) => handleFile((e.target as HTMLInputElement).files?.[0])}
      hidden
    />

    {#if preview}
      <img src={preview} alt={label} />
      <div class="overlay"><span>📁 Ersetzen</span></div>
    {:else}
      <div class="placeholder">
        <span class="icon">🖼️</span>
        <strong>{label}</strong>
        <span class="hint">Drag & Drop oder klicken</span>
        <span class="formats">JPG · PNG · WEBP · max. 10 MB</span>
      </div>
    {/if}
  </div>

  {#if error}
    <p class="error">{error}</p>
  {/if}
</div>

<style>
  .field-wrapper { display: flex; flex-direction: column; gap: 0.4rem; }

  .field-label {
    font-size: 0.82rem;
    font-weight: 600;
    color: #444;
  }
  .required { color: #dc3545; }

  .drop-zone {
    border: 2px dashed #c8cdd4;
    border-radius: 10px;
    height: 200px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    transition: border-color 0.15s, background 0.15s;
    background: #fafbfc;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .drop-zone:hover, .drop-zone.dragging {
    border-color: #0066cc;
    background: #f0f6ff;
  }
  .drop-zone.has-preview { border-style: solid; background: #000; }

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }

  .overlay {
    position: absolute;
    inset: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: opacity 0.15s;
  }
  .drop-zone:hover .overlay { opacity: 1; }
  .overlay span {
    color: white;
    font-weight: 600;
    font-size: 0.95rem;
    background: rgba(0,0,0,0.6);
    padding: 0.4rem 0.9rem;
    border-radius: 20px;
  }

  .placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.3rem;
    color: #6c757d;
    user-select: none;
  }
  .icon { font-size: 2rem; }
  .placeholder strong { color: #333; font-size: 0.9rem; }
  .hint { font-size: 0.8rem; }
  .formats { font-size: 0.72rem; color: #aaa; }

  .error {
    font-size: 0.8rem;
    color: #dc3545;
    background: #fff5f5;
    border: 1px solid #fecaca;
    padding: 0.35rem 0.6rem;
    border-radius: 5px;
  }
</style>
