<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { socket } from '$lib/socket';
  import { api } from '$lib/api'; // still used for loadGame
  import { adminToken } from '$lib/stores/auth';
  import type { Game, Round, Participant } from '$lib/types';
  import ImageCompareSlider from '$lib/components/ImageCompareSlider.svelte';
  import RoundFormModal from '$lib/components/admin/RoundFormModal.svelte';
  import Sortable from 'sortablejs';

  const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
  $: uuid = $page.params.uuid;

  let game: Game | null = null;
  let connected = false;
  let error = '';

  type Phase = 'waiting' | 'round' | 'buzzed' | 'quiz' | 'result' | 'revealed';
  let phase: Phase = 'waiting';

  let currentRound: Round | null = null;

  let buzzedParticipant: { id: number; username: string } | null = null;

  let quizTimeLeft = 0;
  let quizTimer: ReturnType<typeof setInterval> | null = null;

  let participants: Participant[] = [];
  type PlayerCardState = 'idle' | 'buzzed' | 'correct' | 'wrong';
  let playerCardStates: Record<number, PlayerCardState> = {};

  function getPlayerCardState(participantId: number): PlayerCardState {
    return playerCardStates[participantId] ?? 'idle';
  }

  function setPlayerCardState(participantId: number, state: Exclude<PlayerCardState, 'idle'>) {
    playerCardStates = { ...playerCardStates, [participantId]: state };
  }

  function resetPlayerCardStates() {
    playerCardStates = {};
  }

  function resolveUrl(url: string): string {
    return url.startsWith('http') ? url : `${BACKEND}${url}`;
  }

  function playSound(src: string) {
    if (!buzzerSoundEnabled) return;
    const audio = new Audio(src);
    audio.play().catch(() => {});
  }

  function emit(act: string, extra: Record<string, unknown> = {}) {
    socket.emit('admin_action', { game_uuid: uuid, admin_token: $adminToken, action: act, ...extra });
  }

  function nextRound() { emit('next_round'); }

  function correct() {
    if (!buzzedParticipant || !currentRound) return;
    playSound('/correct.mp3');
    setPlayerCardState(buzzedParticipant.id, 'correct');
    emit('correct', { participant_id: buzzedParticipant.id, round_id: currentRound.id });
    phase = 'quiz';
  }

  function wrong() {
    if (!buzzedParticipant || !currentRound) return;
    playSound('/wrong.mp3');
    setPlayerCardState(buzzedParticipant.id, 'wrong');
    emit('wrong', { participant_id: buzzedParticipant.id, round_id: currentRound.id });
    buzzedParticipant = null;
    phase = 'round';
  }

  function unlockAll() {
    emit('unlock_all', { round_id: currentRound?.id });
    buzzedParticipant = null;
    if (phase === 'buzzed') phase = 'round';
  }

  function reveal() {
    if (!currentRound) return;
    emit('reveal', { round_id: currentRound.id });
    phase = 'revealed';
  }

  function skip() {
    if (!currentRound) return;
    emit('skip', { round_id: currentRound.id });
    phase = 'revealed';
  }

  function resetGame() {
    if (!confirm('Spiel wirklich auf Runde 1 zurücksetzen? Alle Punkte werden gelöscht.')) return;
    emit('reset_game');
    phase = 'waiting';
    currentRound = null;
    buzzedParticipant = null;
    if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
  }

  function endGame() {
    emit('end_game');
    goto(`/admin/${uuid}`);
  }

  function focusInput(node: HTMLInputElement) {
    tick().then(() => { node.focus(); node.select(); });
  }

  // Inline score editing
  let buzzerSoundEnabled = true;

  const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
  let exporting = false;

  async function exportGame() {
    exporting = true;
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
    } catch {
      // silently ignore
    } finally {
      exporting = false;
    }
  }

  function toggleBuzzerSound() {
    buzzerSoundEnabled = !buzzerSoundEnabled;
    emit('set_buzzer_sound', { enabled: buzzerSoundEnabled });
  }

  let editingScoreId: number | null = null;
  let editingScoreValue = '';

  function startEditScore(id: number, currentScore: number) {
    editingScoreId = id;
    editingScoreValue = String(currentScore);
  }

  function saveScore(id: number) {
    const score = parseInt(editingScoreValue, 10);
    if (!isNaN(score)) {
      emit('set_score', { participant_id: id, score });
    }
    editingScoreId = null;
  }

  function cancelEditScore() {
    editingScoreId = null;
  }

  // Round strip editing
  let showRoundForm = false;
  let editingRound: Round | null = null;

  function openEditRound(round: Round) {
    if (currentRound?.id === round.id) return;
    editingRound = round;
    showRoundForm = true;
  }

  async function deleteRound(round: Round) {
    if (!confirm(`Runde wirklich löschen? Das kann nicht rückgängig gemacht werden.`)) return;
    try {
      await api.delete(`/api/games/${uuid}/rounds/${round.id}`);
      if (game) game = { ...game, rounds: game.rounds.filter(r => r.id !== round.id) };
    } catch (e: any) {
      error = e.message;
    }
  }

  function onRoundSave(evt: CustomEvent<Round>) {
    showRoundForm = false;
    const saved = evt.detail;
    if (!game) return;
    const idx = game.rounds.findIndex((r) => r.id === saved.id);
    if (idx >= 0) {
      const rounds = [...game.rounds];
      rounds[idx] = saved;
      game = { ...game, rounds };
      if (currentRound?.id === saved.id) currentRound = saved;
    }
  }

  function initStripSortable(node: HTMLElement) {
    const sortable = Sortable.create(node, {
      animation: 150,
      direction: 'horizontal',
      ghostClass: 'strip-ghost',
      chosenClass: 'strip-chosen',
      filter: '.strip-active, .strip-add-tile',
      onEnd: async (evt) => {
        if (evt.oldIndex === evt.newIndex || !game) return;
        const reordered = [...game.rounds];
        const [moved] = reordered.splice(evt.oldIndex!, 1);
        reordered.splice(evt.newIndex!, 0, moved);
        game = { ...game, rounds: reordered.map((r, i) => ({ ...r, position: i })) };
        await Promise.all(
          reordered.map((r, i) => api.patch(`/api/games/${uuid}/rounds/${r.id}`, { position: i }))
        );
      },
    });
    return { destroy: () => sortable.destroy() };
  }

  function kickParticipant(id: number) {
    socket.emit('admin_action', { game_uuid: uuid, admin_token: $adminToken, action: 'kick', participant_id: id });
    participants = participants.filter((p) => p.id !== id); // optimistic
    const { [id]: _removed, ...rest } = playerCardStates;
    playerCardStates = rest;
  }

  function handleKey(e: KeyboardEvent) {
    if ((e.target as HTMLElement).tagName === 'INPUT') return;
    switch (e.key) {
      case ' ': e.preventDefault(); handleNextOrEnd(); break;
      case 'c': case 'C': correct(); break;
      case 'w': case 'W': wrong(); break;
      case 'r': case 'R': reveal(); break;
      case 's': case 'S': skip(); break;
    }
  }

  onMount(async () => {
    if (!$adminToken) { goto('/admin'); return; }

    try {
      game = await api.get(`/api/games/${uuid}`);
      participants = game?.participants ?? [];
    } catch (e: any) {
      error = e.message;
      return;
    }

    socket.connect();
    socket.emit('join_admin', { game_uuid: uuid, admin_token: $adminToken });

    socket.on('joined_admin', (data) => {
      connected = true;
      if (!game) return;

      // Restore round
      if (data.current_round_id) {
        currentRound = game.rounds.find((r) => r.id === data.current_round_id) ?? null;
      }

      // Restore phase
      const p = data.present_phase as string | null;
      if (p === 'round')    phase = 'round';
      else if (p === 'buzzed') {
        phase = 'buzzed';
        if (data.buzzer_winner) {
          buzzedParticipant = data.buzzer_winner;
          setPlayerCardState(data.buzzer_winner.id, 'buzzed');
        }
      }
      else if (p === 'quiz') {
        phase = 'quiz';
        if (data.quiz_time_left != null) {
          quizTimeLeft = data.quiz_time_left;
          if (quizTimer) clearInterval(quizTimer);
          quizTimer = setInterval(() => {
            quizTimeLeft = Math.max(0, quizTimeLeft - 1);
            if (quizTimeLeft === 0) { clearInterval(quizTimer!); quizTimer = null; }
          }, 1000);
        }
      }
      else if (p === 'revealed') phase = 'revealed';
    });

    socket.on('round_start', (data) => {
      currentRound = game?.rounds.find((r) => r.id === data.round_id) ?? null;
      buzzedParticipant = null;
      resetPlayerCardStates();
      phase = 'round';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('buzz_received', (data) => {
      buzzedParticipant = { id: data.participant_id, username: data.username };
      setPlayerCardState(data.participant_id, 'buzzed');
      phase = 'buzzed';
    });

    socket.on('quiz_start', (data) => {
      phase = 'quiz';
      quizTimeLeft = data.time_limit;
      if (quizTimer) clearInterval(quizTimer);
      quizTimer = setInterval(() => {
        quizTimeLeft = Math.max(0, quizTimeLeft - 1);
        if (quizTimeLeft === 0) { clearInterval(quizTimer!); quizTimer = null; }
      }, 1000);
    });

    socket.on('quiz_result', (data) => {
      const stateById = new Map(participants.map((p) => [p.id, { ready: p.ready, locked: p.locked }]));
      participants = data.leaderboard.map((x: any) => ({
        id: x.participant_id,
        username: x.username,
        score: x.score,
        ready: stateById.get(x.participant_id)?.ready ?? false,
        locked: stateById.get(x.participant_id)?.locked ?? false,
      }));
      phase = 'result';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('round_end', () => {
      buzzedParticipant = null;
      phase = 'revealed';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('participants_update', (data: { participants: Participant[] }) => {
      participants = data.participants;
    });

    socket.on('game_reset', () => {
      phase = 'waiting';
      currentRound = null;
      buzzedParticipant = null;
      resetPlayerCardStates();
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('game_end', () => {
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
      goto(`/admin/${uuid}`);
    });

    window.addEventListener('keydown', handleKey);
  });

  onDestroy(() => {
    if (quizTimer) clearInterval(quizTimer);
    window.removeEventListener('keydown', handleKey);
    socket.off('joined_admin');
    socket.off('round_start');
    socket.off('buzz_received');
    socket.off('quiz_start');
    socket.off('quiz_result');
    socket.off('round_end');
    socket.off('participants_update');
    socket.off('game_reset');
    socket.off('game_end');
    socket.disconnect();
  });

  $: aiImageUrl = currentRound?.ai_url ? resolveUrl(currentRound.ai_url) : null;
  $: originalImageUrl = currentRound?.original_url ? resolveUrl(currentRound.original_url) : null;
  $: correctLocation = currentRound?.locations.find((l) => l.is_correct) ?? null;
  $: currentRoundIndex = (currentRound && game) ? game.rounds.findIndex((r) => r.id === currentRound!.id) : -1;
  $: roundLabel = game && currentRoundIndex >= 0
    ? `Runde ${currentRoundIndex + 1} / ${game.rounds.length}`
    : '–';
  $: sortedParticipants = [...participants].sort((a, b) => b.score - a.score);
  $: isLastRound = game !== null && currentRoundIndex >= 0 && currentRoundIndex === game.rounds.length - 1;
  $: showEndButton = isLastRound && (phase === 'revealed' || phase === 'result');

  const phaseBadgeLabel: Record<Phase, string> = {
    waiting: 'Bereit',
    round: 'Runde läuft',
    buzzed: 'Buzzer!',
    quiz: 'Quiz läuft',
    result: 'Quiz beendet',
    revealed: 'Aufgelöst',
  };

  function handleNextOrEnd() {
    if (showEndButton) endGame();
    else nextRound();
  }
</script>

{#if error}
  <p class="error-msg">{error}</p>
{:else}
  <div class="master">
    <header>
      <a href="/admin/{uuid}" class="back">← Übersicht</a>
      <div class="title-area">
        <h1>{game?.title ?? '…'}</h1>
        <span class="round-badge">{roundLabel}</span>
      </div>
      <div class="conn" class:online={connected}>
        {connected ? '● Live' : '○ Verbinde…'}
      </div>
      <button class="btn-export" on:click={exportGame} disabled={exporting}>
        {exporting ? '…' : '⬇ Export'}
      </button>
      <button class="btn-reset" on:click={resetGame}>↺ Zurücksetzen</button>
    </header>

    <div class="layout">
      <!-- Left column: image + GM solution -->
      <div class="left-col">
        <div class="panel">
          <div class="panel-title">Aktuelle Runde</div>
          <div class="round-img-wrapper">
            {#if aiImageUrl && originalImageUrl}
              <ImageCompareSlider aiUrl={aiImageUrl} originalUrl={originalImageUrl} />
            {:else if aiImageUrl}
              <img src={aiImageUrl} alt="KI-Bild" class="round-img" />
            {:else}
              <div class="no-img">Keine Runde aktiv</div>
            {/if}
          </div>

          {#if currentRound}
            <div class="round-meta">
              <span>⏱ {currentRound.time_limit}s Quizzeit</span>
              {#if currentRound.target_year}
                <span>📅 Ziel: {currentRound.target_year}</span>
              {/if}
            </div>

            <div class="gm-solution">
              {#if correctLocation}
                <div class="gm-answer">
                  <span class="gm-answer-label">📍 Richtige Location</span>
                  <span class="gm-answer-value">{correctLocation.name}</span>
                </div>
              {/if}
              {#if currentRound.target_year}
                <div class="gm-answer">
                  <span class="gm-answer-label">📅 Ziel-Jahr</span>
                  <span class="gm-answer-value gm-year">{currentRound.target_year}</span>
                </div>
              {/if}
              {#if currentRound.solution_text}
                <div class="gm-hint">
                  <span class="gm-answer-label">💡 Hinweis</span>
                  <p class="gm-hint-text">{currentRound.solution_text}</p>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      </div>

      <!-- Middle column: players + buzzer + scores -->
      <div class="mid-col">
        <div class="panel">
          <div class="panel-title">Teilnehmer</div>
          {#if sortedParticipants.length === 0}
            <p class="muted">Noch keine Teilnehmer</p>
          {:else}
            <div class="player-grid">
              {#each sortedParticipants as p, i (p.id)}
                <div
                  class="player-card"
                  class:card-buzzed={getPlayerCardState(p.id) === 'buzzed'}
                  class:card-correct={getPlayerCardState(p.id) === 'correct'}
                  class:card-wrong={getPlayerCardState(p.id) === 'wrong'}
                >
                  <span class="card-rank">{i + 1}.</span>
                  <button class="kick-btn card-kick" title="Spieler entfernen" on:click={() => kickParticipant(p.id)}>✕</button>
                  <span class="card-name" class:ready={p.ready}>{p.username}</span>
                  {#if editingScoreId === p.id}
                    <input
                      class="score-input"
                      type="number"
                      bind:value={editingScoreValue}
                      on:keydown={(e) => { if (e.key === 'Enter') saveScore(p.id); if (e.key === 'Escape') cancelEditScore(); }}
                      on:blur={() => saveScore(p.id)}
                      use:focusInput
                    />
                  {:else}
                    <button class="pts-btn card-pts" on:click={() => startEditScore(p.id, p.score)}>
                      {p.score} Pkt
                    </button>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>

        {#if phase === 'buzzed'}
          <div class="panel buzzer-panel">
            <div class="panel-title">🔔 Buzzer</div>
            <p class="buzz-who">{buzzedParticipant?.username}</p>
            <div class="buzz-actions">
              <button class="btn-correct" on:click={correct}>✓ Richtig <kbd>C</kbd></button>
              <button class="btn-wrong" on:click={wrong}>✗ Falsch <kbd>W</kbd></button>
            </div>
          </div>
        {:else if phase === 'quiz'}
          <div class="panel quiz-panel">
            <div class="panel-title">Quiz läuft</div>
            <div class="quiz-timer">{quizTimeLeft}s</div>
          </div>
        {/if}
      </div>

      <!-- Right column: controls + shortcuts -->
      <div class="right-col">
        <div class="panel">
          <div class="panel-title panel-title-row">
            Steuerung
            <span class="phase-badge phase-{phase}">● {phaseBadgeLabel[phase]}</span>
          </div>
          <div class="ctrl-grid">
            <button class="btn-primary span2" class:btn-end-game={showEndButton} on:click={handleNextOrEnd}>
              {showEndButton ? '■ Spiel beenden' : phase === 'waiting' ? '▶ Spiel starten' : '▶ Nächste Runde'}
            </button>
            <button class="btn-secondary" on:click={reveal}
              disabled={!currentRound || phase === 'revealed' || phase === 'waiting'}>
              👁 Auflösen
            </button>
            <button class="btn-secondary" on:click={skip}
              disabled={!currentRound || phase === 'revealed' || phase === 'waiting'}>
              ⏭ Überspringen
            </button>
            <button class="btn-secondary" on:click={unlockAll} disabled={!currentRound}>
              🔓 Alle entsperren
            </button>
            <button class="btn-sound" class:sound-off={!buzzerSoundEnabled} on:click={toggleBuzzerSound}>
              {buzzerSoundEnabled ? '🔔 Sound an' : '🔕 Sound aus'}
            </button>
            <button class="btn-end-early span2" on:click={endGame}>■ Spiel beenden</button>
          </div>
        </div>

        <div class="panel shortcuts">
          <div class="panel-title">Tastenkürzel</div>
          <div class="shortcut-list">
            <div><kbd>Space</kbd><span>Nächste Runde</span></div>
            <div><kbd>C</kbd><span>Richtig</span></div>
            <div><kbd>W</kbd><span>Falsch</span></div>
            <div><kbd>R</kbd><span>Auflösen</span></div>
            <div><kbd>S</kbd><span>Überspringen</span></div>
            <div></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Round strip -->
    {#if game && game.rounds.length > 0}
      <div class="strip-panel">
        <div class="strip-header">
          <span class="strip-title">Alle Runden</span>
          <span class="strip-hint">Ziehen zum Sortieren</span>
        </div>
        <div class="round-strip" use:initStripSortable>
          {#each game.rounds as round, i (round.id)}
            <div
              class="strip-tile"
              class:strip-active={currentRound?.id === round.id}
            >
              <div class="strip-num">
                {#if currentRound?.id === round.id}▶ {/if}Runde {i + 1}
              </div>
              {#if round.ai_url}
                <img src={resolveUrl(round.ai_url)} alt="Runde {i + 1}" class="strip-thumb" draggable="false" />
              {:else}
                <div class="strip-no-img">kein Bild</div>
              {/if}
              {#if currentRound?.id === round.id}
                <div class="strip-lock" title="Aktive Runde – nicht bearbeitbar">🔒</div>
              {:else}
                <div class="strip-actions">
                  <button class="strip-edit-btn" title="Bearbeiten" on:click|stopPropagation={() => openEditRound(round)}>✏️</button>
                  <button class="strip-del-btn" title="Löschen" on:click|stopPropagation={() => deleteRound(round)}>🗑</button>
                </div>
              {/if}
            </div>
          {/each}
          <button class="strip-add-tile" title="Neue Runde anlegen" on:click={() => { editingRound = null; showRoundForm = true; }}>
            <span class="strip-add-icon">+</span>
          </button>
        </div>
      </div>
    {/if}
  </div>
{/if}

{#if showRoundForm}
  <RoundFormModal
    gameUuid={uuid}
    round={editingRound}
    on:save={onRoundSave}
    on:close={() => (showRoundForm = false)}
  />
{/if}

<style>
  .error-msg {
    color: #dc3545;
    background: #fff5f5;
    border: 1px solid #fecaca;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-top: 1rem;
  }

  .master {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  /* Header */
  header {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: white;
    border-radius: 12px;
    padding: 0.85rem 1.25rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }

  .back {
    color: #0066cc;
    text-decoration: none;
    font-size: 0.88rem;
    font-weight: 600;
    white-space: nowrap;
  }
  .back:hover { text-decoration: underline; }

  .title-area {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
  }

  h1 {
    font-size: 1.15rem;
    color: #1a1a2e;
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .round-badge {
    font-size: 0.78rem;
    font-weight: 700;
    background: #f0f2f5;
    color: #555;
    padding: 0.2rem 0.65rem;
    border-radius: 20px;
    white-space: nowrap;
  }

  .conn {
    font-size: 0.8rem;
    font-weight: 600;
    color: #aaa;
    white-space: nowrap;
  }
  .conn.online { color: #28a745; }

  .btn-export {
    background: #f0f2f5;
    color: #444;
    border: 1.5px solid #d0d5dd;
    border-radius: 8px;
    padding: 0.45rem 0.9rem;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s;
  }
  .btn-export:hover:not(:disabled) { background: #e0e3e8; }
  .btn-export:disabled { opacity: 0.5; cursor: not-allowed; }

  .btn-reset {
    background: #f0a500;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.45rem 0.9rem;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-reset:hover { background: #d48e00; }

  /* Layout */
  .layout {
    display: grid;
    grid-template-columns: 1fr 1fr 320px;
    gap: 1.25rem;
    align-items: stretch;
  }

  @media (max-width: 1200px) {
    .layout { grid-template-columns: 1fr 1fr; }
    .right-col { grid-column: 1 / -1; display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
  }

  @media (max-width: 700px) {
    .layout { grid-template-columns: 1fr; }
    .right-col { grid-column: unset; display: flex; }
  }

  .left-col, .mid-col, .right-col {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    min-height: 0;
  }

  /* Let the main panel in each column grow to fill column height */
  .left-col > .panel { flex: 1; }
  .mid-col > .panel:first-child { flex: 1; }
  .right-col .shortcuts { flex: 1; }

  /* Panel */
  .panel {
    background: white;
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }

  .panel-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 0.75rem;
  }

  .round-img-wrapper {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    border-radius: 8px;
  }

  .round-img-wrapper :global(.compare) {
    width: 100% !important;
    height: 100% !important;
    aspect-ratio: unset !important;
  }

  .round-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  /* Game master solution info */
  .gm-solution {
    margin-top: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    border-top: 1px solid #f0f2f5;
    padding-top: 0.75rem;
  }

  .gm-answer {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .gm-answer-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    white-space: nowrap;
  }

  .gm-answer-value {
    font-size: 0.95rem;
    font-weight: 700;
    color: #1a1a2e;
  }

  .gm-year {
    color: #0066cc;
    font-size: 1.05rem;
  }

  .gm-hint {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .gm-hint-text {
    font-size: 0.82rem;
    color: #555;
    line-height: 1.5;
    margin: 0;
    background: #f8f9fa;
    border-left: 3px solid #f0a500;
    padding: 0.4rem 0.6rem;
    border-radius: 0 6px 6px 0;
  }

  .no-img {
    width: 100%;
    height: 100%;
    background: #f0f2f5;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #aaa;
    font-size: 0.9rem;
  }

  .round-meta {
    display: flex;
    gap: 1rem;
    margin-top: 0.6rem;
    font-size: 0.82rem;
    color: #666;
  }

  .muted { color: #aaa; font-size: 0.88rem; margin: 0; }


  .pts-btn {
    background: none;
    border: 1px solid transparent;
    border-radius: 6px;
    color: #0066cc;
    font-weight: 700;
    font-size: 0.9rem;
    cursor: pointer;
    padding: 0.1rem 0.35rem;
    white-space: nowrap;
    transition: background 0.1s, border-color 0.1s;
  }
  .pts-btn:hover { background: #f0f6ff; border-color: #c0d8f8; }

  .score-input {
    width: 5rem;
    border: 1.5px solid #0066cc;
    border-radius: 6px;
    padding: 0.15rem 0.4rem;
    font-size: 0.9rem;
    font-weight: 700;
    color: #0066cc;
    text-align: right;
    outline: none;
  }
  .kick-btn {
    background: none;
    border: 1px solid #fecaca;
    border-radius: 4px;
    color: #dc3545;
    cursor: pointer;
    font-size: 0.72rem;
    line-height: 1;
    padding: 0.15rem 0.35rem;
    opacity: 0.6;
    transition: opacity 0.1s, background 0.1s;
  }
  .kick-btn:hover { opacity: 1; background: #fff5f5; }

  /* Buzzer panel */
  .buzzer-panel {
    border: 2px solid #ffd700;
    background: #fffdf0;
  }

  .buzz-who {
    font-size: 1.6rem;
    font-weight: 900;
    color: #1a1a2e;
    margin: 0.25rem 0 1rem;
    text-align: center;
  }

  .buzz-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
  }

  .btn-correct {
    background: #28a745;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.75rem;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
  }
  .btn-correct:hover { background: #218838; }

  .btn-wrong {
    background: #dc3545;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.75rem;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
  }
  .btn-wrong:hover { background: #c82333; }

  /* Quiz panel */
  .quiz-panel {
    border: 2px solid #0066cc;
    background: #f0f6ff;
    text-align: center;
  }
  .quiz-timer {
    font-size: 3rem;
    font-weight: 900;
    color: #0066cc;
    line-height: 1;
  }

  .player-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
    gap: 0.5rem;
  }

  .player-card {
    position: relative;
    min-height: 80px;
    border-radius: 10px;
    border: 1.5px solid #dfe3e8;
    background: #f8fafc;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.35rem 0.35rem 0.45rem;
    gap: 0.1rem;
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    overflow: hidden;
  }

  .card-rank {
    font-size: 0.6rem;
    font-weight: 700;
    color: #bbb;
    align-self: flex-start;
    line-height: 1;
  }

  .card-name {
    font-size: 0.82rem;
    font-weight: 700;
    color: #1f2937;
    text-align: center;
    overflow-wrap: anywhere;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
  }
  .card-name.ready { color: #28a745; }

  .card-kick {
    position: absolute;
    top: 0.2rem;
    right: 0.2rem;
    opacity: 0;
    transition: opacity 0.15s;
  }
  .player-card:hover .card-kick { opacity: 1; }

  .card-pts {
    font-size: 0.72rem;
    padding: 0.08rem 0.25rem;
  }

  .player-card.card-buzzed {
    background: #fef3c7;
    border-color: #f59e0b;
    color: #92400e;
  }

  .player-card.card-correct {
    background: #dcfce7;
    border-color: #22c55e;
    color: #166534;
  }

  .player-card.card-wrong {
    background: #fee2e2;
    border-color: #ef4444;
    color: #991b1b;
  }

  /* Controls */
  .ctrl-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
    min-width: 0;
  }

  .ctrl-grid button {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .btn-primary {
    background: #1a1a2e;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
  }
  .btn-primary:hover { opacity: 0.85; }
  .btn-end-game { background: #dc3545; }
  .btn-end-game:hover { background: #c82333; opacity: 1; }

  .btn-end-early {
    background: none;
    color: #dc3545;
    border: 1.5px solid #fecaca;
    border-radius: 8px;
    padding: 0.55rem;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .btn-end-early:hover { background: #fff5f5; border-color: #dc3545; }

  .btn-secondary {
    background: #f0f2f5;
    color: #333;
    border: 1px solid #e0e3e8;
    border-radius: 8px;
    padding: 0.65rem 0.8rem;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
  }
  .btn-secondary:hover:not(:disabled) { background: #e0e3e8; }
  .btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }

  .span2 { grid-column: 1 / -1; }

  .btn-sound {
    background: #e8f5e9;
    color: #2e7d32;
    border: 1px solid #a5d6a7;
    border-radius: 8px;
    padding: 0.65rem 0.8rem;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    transition: background 0.15s;
  }
  .btn-sound:hover { background: #c8e6c9; }
  .btn-sound.sound-off { background: #fce4ec; color: #b71c1c; border-color: #ef9a9a; }
  .btn-sound.sound-off:hover { background: #f8bbd0; }

  /* Shortcuts */
  .shortcuts { background: #f8f9fa; }
  .shortcut-list {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.35rem 0.75rem;
  }
  .shortcut-list > div {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: #555;
  }

  /* Phase badge in controls title */
  .panel-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .phase-badge {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 0.15rem 0.55rem;
    border-radius: 20px;
    text-transform: none;
    letter-spacing: 0;
  }
  .phase-waiting  { background: #e5e7eb; color: #6b7280; }
  .phase-round    { background: #dbeafe; color: #1d4ed8; }
  .phase-buzzed   { background: #fef3c7; color: #92400e; }
  .phase-quiz     { background: #ede9fe; color: #6d28d9; }
  .phase-result   { background: #dcfce7; color: #166534; }
  .phase-revealed { background: #dcfce7; color: #166534; }

  /* Round strip */
  .strip-panel {
    background: white;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }

  .strip-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }

  .strip-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .strip-hint {
    font-size: 0.7rem;
    color: #bbb;
  }

  .round-strip {
    display: flex;
    gap: 0.75rem;
    overflow-x: auto;
    padding-bottom: 0.4rem;
    scrollbar-width: thin;
    scrollbar-color: #ddd transparent;
  }

  .strip-tile {
    flex: 0 0 130px;
    position: relative;
    border-radius: 8px;
    border: 2px solid #e0e3e8;
    background: #f8fafc;
    overflow: hidden;
    cursor: grab;
    transition: border-color 0.15s, box-shadow 0.15s;
    user-select: none;
  }
  .strip-tile:hover { border-color: #b0b8c8; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .strip-tile.strip-active {
    border-color: #1a1a2e;
    box-shadow: 0 0 0 2px rgba(26,26,46,0.18);
  }

  .strip-num {
    font-size: 0.65rem;
    font-weight: 700;
    color: #999;
    padding: 0.3rem 0.5rem 0.2rem;
    background: white;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .strip-tile.strip-active .strip-num { color: #1a1a2e; }

  .strip-thumb {
    width: 100%;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    display: block;
  }

  .strip-no-img {
    width: 100%;
    aspect-ratio: 16 / 9;
    background: #f0f2f5;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ccc;
    font-size: 0.75rem;
  }

  .strip-actions {
    position: absolute;
    top: 0.25rem;
    right: 0.25rem;
    display: flex;
    gap: 0.2rem;
    opacity: 0;
    transition: opacity 0.15s;
    z-index: 1;
  }
  .strip-tile:hover .strip-actions { opacity: 1; }

  .strip-edit-btn, .strip-del-btn {
    background: rgba(255,255,255,0.92);
    border: 1px solid #e0e3e8;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.7rem;
    padding: 0.15rem 0.3rem;
    line-height: 1;
  }
  .strip-del-btn:hover { background: #fff0f0; border-color: #fecaca; }

  .strip-lock {
    position: absolute;
    top: 0.25rem;
    right: 0.25rem;
    font-size: 0.75rem;
    line-height: 1;
    opacity: 0.7;
    pointer-events: none;
  }

  .strip-add-tile {
    flex: 0 0 130px;
    align-self: stretch;
    border-radius: 8px;
    border: 2px dashed #c8cdd4;
    background: transparent;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: border-color 0.15s, background 0.15s;
    color: #aab0bb;
    padding: 0;
  }
  .strip-add-tile:hover {
    border-color: #0066cc;
    background: #f0f6ff;
    color: #0066cc;
  }

  .strip-add-icon {
    font-size: 1.6rem;
    font-weight: 300;
    line-height: 1;
  }

  .strip-active { cursor: default; }

  :global(.strip-ghost) { opacity: 0.35; }
  :global(.strip-chosen) { cursor: grabbing !important; }

  kbd {
    background: #e0e3e8;
    border-radius: 4px;
    padding: 0.1rem 0.4rem;
    font-size: 0.75rem;
    font-family: monospace;
    font-weight: 700;
    color: #333;
    border: 1px solid #ccc;
    min-width: 1.8rem;
    text-align: center;
  }
</style>
