<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { api, uploadImages } from '$lib/api';
  import ImageUploadField from './ImageUploadField.svelte';
  import type { Round } from '$lib/types';

  export let gameUuid: string;
  export let round: Round | null = null; // null = create mode

  const dispatch = createEventDispatcher<{ save: Round; close: void }>();

  const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';

  // Form state
  let solutionText = round?.solution_text ?? '';
  let targetYear: number | '' = round?.target_year ?? '';
  let timeLimit = Math.round((Math.min(45, Math.max(15, round?.time_limit ?? 20))) / 5) * 5;

  // Locations
  let useLocations = (round?.locations.length ?? 0) > 0;
  let locations: { name: string; is_correct: boolean }[] = round?.locations && round.locations.length > 0
    ? round.locations.map((l) => ({ name: l.name, is_correct: l.is_correct }))
    : [
        { name: '', is_correct: true },
        { name: '', is_correct: false },
        { name: '', is_correct: false },
        { name: '', is_correct: false },
      ];

  // Images
  let originalFile: File | null = null;
  let aiFile: File | null = null;
  let originalPreview = round?.original_url
    ? round.original_url.startsWith('http') ? round.original_url : `${BACKEND}${round.original_url}`
    : '';
  let aiPreview = round?.ai_url
    ? round.ai_url.startsWith('http') ? round.ai_url : `${BACKEND}${round.ai_url}`
    : '';
  let originalFilename: string | null = round?.original_filename ?? null;
  let aiFilename: string | null = round?.ai_filename ?? null;
  let uploadImageError = '';

  // Progress
  let uploadProgress = 0;
  let saving = false;
  let generalError = '';

  function setCorrect(i: number) {
    locations = locations.map((l, idx) => ({ ...l, is_correct: idx === i }));
  }

  $: yearValid = targetYear === '' || (Number(targetYear) > 1800 && Number(targetYear) <= new Date().getFullYear() + 1);
  $: locationsValid = !useLocations || (locations.every((l) => l.name.trim() !== '') && locations.some((l) => l.is_correct));
  $: isValid =
    solutionText.trim() !== '' &&
    yearValid &&
    locationsValid &&
    (round !== null || (!!originalFile && !!aiFile));  // images required only for new rounds

  async function save() {
    if (!isValid || saving) return;
    saving = true;
    generalError = '';
    uploadProgress = 0;

    try {
      let savedRound: Round;

      const roundData: Record<string, unknown> = {
        solution_text: solutionText.trim(),
        time_limit: timeLimit,
        ...(targetYear !== '' ? { target_year: Number(targetYear) } : { target_year: null }),
      };

      if (round === null) {
        savedRound = await api.post(`/api/games/${gameUuid}/rounds`, roundData);
      } else {
        savedRound = await api.patch(`/api/games/${gameUuid}/rounds/${round.id}`, roundData);
      }

      // Upload images if new files are provided
      if (originalFile || aiFile) {
        try {
          const urls = await uploadImages(
            gameUuid,
            savedRound.id,
            originalFile,
            aiFile,
            (pct) => (uploadProgress = pct)
          );
          savedRound.original_url = urls.original_url;
          savedRound.ai_url = urls.ai_url;
        } catch (e: any) {
          uploadImageError = e.message;
          saving = false;
          return;
        }
      }

      // Handle locations
      if (useLocations) {
        if (round === null || round.locations.length === 0) {
          // New round or round had no locations: create them
          await api.post(`/api/rounds/${savedRound.id}/locations`, {
            locations: locations.map((l) => ({ name: l.name.trim(), is_correct: l.is_correct })),
          });
        } else {
          // Existing locations: update each one
          for (let i = 0; i < round.locations.length; i++) {
            await api.patch(`/api/rounds/${round.id}/locations/${round.locations[i].id}`, {
              name: locations[i].name.trim(),
              is_correct: locations[i].is_correct,
            });
          }
        }
      } else if (round !== null && round.locations.length > 0) {
        // User removed locations from an existing round
        await api.delete(`/api/rounds/${round.id}/locations`);
      }

      // Reload full round data from server
      const game = await api.get(`/api/games/${gameUuid}`);
      const updated = game.rounds.find((r: Round) => r.id === savedRound.id);
      dispatch('save', updated ?? savedRound);
    } catch (e: any) {
      generalError = e.message;
    } finally {
      saving = false;
    }
  }
</script>

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div class="backdrop" role="dialog" aria-modal="true" on:click|self={() => dispatch('close')}>
  <div class="modal">
    <div class="modal-header">
      <h2>{round ? `Runde bearbeiten` : 'Neue Runde anlegen'}</h2>
      <button class="close" on:click={() => dispatch('close')}>✕</button>
    </div>

    <div class="modal-body">
      <!-- Images -->
      <div class="image-row">
        <div class="img-col">
          <ImageUploadField
            label="Original"
            bind:preview={originalPreview}
            bind:error={uploadImageError}
            on:select={(e) => { originalFile = e.detail; originalFilename = e.detail.name; }}
          />
          <p class="filename">{originalFilename ?? '–'}</p>
        </div>
        <div class="img-col">
          <ImageUploadField
            label="KI-Bild"
            bind:preview={aiPreview}
            error=""
            on:select={(e) => { aiFile = e.detail; aiFilename = e.detail.name; }}
          />
          <p class="filename">{aiFilename ?? '–'}</p>
        </div>
      </div>

      <!-- Upload progress -->
      {#if saving && uploadProgress > 0}
        <div class="progress-wrap">
          <div class="progress-bar" style="width: {uploadProgress}%"></div>
          <span>{uploadProgress}%</span>
        </div>
      {/if}

      <!-- Metadata -->
      <div class="form-grid">
        <label class="full">
          <span style="white-space: nowrap">Auflösungssatz <span class="req">*</span></span>
          <input
            type="text"
            bind:value={solutionText}
            placeholder="z.B. Eine Person wurde hinzugefügt"
          />
        </label>

        <label>
          <span style="white-space: nowrap">Jahr <span class="opt">(optional)</span></span>
          <input
            type="number"
            bind:value={targetYear}
            min="1800"
            max={new Date().getFullYear() + 1}
            placeholder="z.B. 2019"
            class:invalid={!yearValid && targetYear !== ''}
          />
        </label>

        <label>
          <span style="white-space: nowrap">Antwortzeit: <strong>{timeLimit}s</strong></span>
          <input type="range" bind:value={timeLimit} min="15" max="45" step="5" />
          <div class="range-labels"><span>15s</span><span>45s</span></div>
        </label>
      </div>

      <!-- Locations -->
      <div class="locations" class:disabled={!useLocations}>
        <div class="loc-header">
          <span class="loc-title">Ortswahl <span class="opt">(optional)</span></span>
          <button type="button" class="toggle-switch" class:on={useLocations} on:click={() => useLocations = !useLocations} aria-pressed={useLocations}>
            <span class="toggle-knob" />
          </button>
        </div>
        {#if useLocations}
          <div class="loc-grid">
            {#each locations as loc, i}
              <div class="loc-row">
                <input
                  type="radio"
                  name="correct"
                  checked={loc.is_correct}
                  on:change={() => setCorrect(i)}
                  id="loc-{i}"
                  title="Als richtige Antwort markieren"
                />
                <input
                  type="text"
                  bind:value={loc.name}
                  placeholder="Location {i + 1}"
                  class:correct={loc.is_correct}
                />
              </div>
            {/each}
          </div>
          <p class="loc-hint">Radio-Button = richtige Antwort</p>
        {/if}
      </div>

      {#if !useLocations && targetYear === ''}
        <p class="quiz-skip-info">ℹ️ Weder Ortswahl noch Jahr angegeben – die Fragerunde wird für diese Runde übersprungen.</p>
      {/if}

      {#if generalError}
        <p class="error">{generalError}</p>
      {/if}
    </div>

    <div class="modal-footer">
      <button class="btn-cancel" on:click={() => dispatch('close')}>Abbrechen</button>
      <button class="btn-save" disabled={!isValid || saving} on:click={save}>
        {saving ? '💾 Speichere…' : '💾 Speichern'}
      </button>
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 200;
    padding: 1rem;
    backdrop-filter: blur(2px);
  }

  .modal {
    background: white;
    border-radius: 14px;
    width: 100%;
    max-width: 980px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,0.25);
    overflow: hidden;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid #f0f2f5;
    flex-shrink: 0;
  }
  h2 { font-size: 1rem; color: #1a1a2e; }

  .close {
    background: none;
    border: none;
    font-size: 1.1rem;
    cursor: pointer;
    color: #888;
    padding: 0.25rem;
    border-radius: 4px;
  }
  .close:hover { color: #333; background: #f0f2f5; }

  .modal-body {
    overflow-y: auto;
    padding: 0.9rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    flex: 1;
  }

  .image-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }

  .img-col {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .filename {
    font-size: 0.72rem;
    color: #888;
    margin: 0;
    word-break: break-all;
    font-style: italic;
  }

  .progress-wrap {
    background: #f0f2f5;
    border-radius: 8px;
    height: 24px;
    position: relative;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%;
    background: #0066cc;
    transition: width 0.1s;
    border-radius: 8px;
  }
  .progress-wrap span {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 600;
    color: #333;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
  }
  .full { grid-column: 1 / -1; }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: #444;
  }
  .req { color: #dc3545; }
  .opt { color: #888; font-weight: 400; font-size: 0.75rem; }

  input[type="text"], input[type="number"] {
    border: 1.5px solid #d0d5dd;
    border-radius: 7px;
    padding: 0.4rem 0.65rem;
    font-size: 0.9rem;
    transition: border-color 0.15s;
    width: 100%;
  }
  input[type="text"]:focus, input[type="number"]:focus {
    outline: none;
    border-color: #0066cc;
  }

  input[type="range"] { width: 100%; accent-color: #0066cc; }
  .range-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.7rem;
    color: #888;
    font-weight: 400;
  }

  .locations {
    border: 1.5px solid #e0e3e8;
    border-radius: 10px;
    padding: 0.6rem 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .loc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .loc-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: #444;
  }

  /* Toggle switch */
  .toggle-switch {
    position: relative;
    width: 36px;
    height: 20px;
    border-radius: 20px;
    background: #d0d5dd;
    border: none;
    cursor: pointer;
    padding: 0;
    transition: background 0.2s;
    flex-shrink: 0;
  }
  .toggle-switch.on { background: #0066cc; }

  .toggle-knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: white;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    transition: left 0.2s;
  }
  .toggle-switch.on .toggle-knob { left: 19px; }

  .loc-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem;
  }

  .loc-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .loc-row input[type="text"] {
    flex: 1;
    padding: 0.4rem 0.55rem;
  }
  .loc-row input[type="text"].correct { border-color: #28a745; background: #f6fff8; }

  .loc-row input[type="radio"] { cursor: pointer; accent-color: #28a745; }

  .loc-hint { font-size: 0.72rem; color: #888; font-weight: 400; margin: 0; }

  .locations.disabled { opacity: 0.6; pointer-events: none; }
  .locations.disabled .loc-header { pointer-events: auto; }

  .quiz-skip-info {
    font-size: 0.82rem;
    color: #555;
    background: #fffbeb;
    border: 1px solid #fde68a;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
  }

  input.invalid { border-color: #dc3545; }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 0.6rem;
    padding: 0.65rem 1.25rem;
    border-top: 1px solid #f0f2f5;
    flex-shrink: 0;
  }

  .btn-cancel {
    background: #f0f2f5;
    color: #333;
    border: none;
    border-radius: 8px;
    padding: 0.6rem 1.2rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-cancel:hover { background: #e0e3e8; }

  .btn-save {
    background: #1a1a2e;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.6rem 1.4rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .btn-save:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-save:not(:disabled):hover { opacity: 0.85; }

  .error {
    font-size: 0.82rem;
    color: #dc3545;
    background: #fff5f5;
    border: 1px solid #fecaca;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
  }

  @media (max-width: 600px) {
    .image-row, .form-grid { grid-template-columns: 1fr; }
    .full { grid-column: 1; }
  }
</style>
