<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { socket } from '$lib/socket';
  import { api } from '$lib/api'; // still used for loadGame
  import { adminToken } from '$lib/stores/auth';
  import type { Game, Round, Participant } from '$lib/types';

  const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
  $: uuid = $page.params.uuid;

  let game: Game | null = null;
  let connected = false;
  let error = '';

  type Phase = 'waiting' | 'round' | 'buzzed' | 'quiz' | 'result' | 'revealed';
  let phase: Phase = 'waiting';

  let currentRound: Round | null = null;
  let currentRoundIndex = -1;

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

  function emit(act: string, extra: Record<string, unknown> = {}) {
    socket.emit('admin_action', { game_uuid: uuid, admin_token: $adminToken, action: act, ...extra });
  }

  function nextRound() { emit('next_round'); }

  function correct() {
    if (!buzzedParticipant || !currentRound) return;
    setPlayerCardState(buzzedParticipant.id, 'correct');
    emit('correct', { participant_id: buzzedParticipant.id, round_id: currentRound.id });
    phase = 'quiz';
  }

  function wrong() {
    if (!buzzedParticipant || !currentRound) return;
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
    currentRoundIndex = -1;
    buzzedParticipant = null;
    if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
  }

  function endGame() {
    emit('end_game');
    goto(`/admin/${uuid}`);
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
      case ' ': e.preventDefault(); nextRound(); break;
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

    socket.on('joined_admin', () => { connected = true; });

    socket.on('round_start', (data) => {
      currentRound = game?.rounds.find((r) => r.id === data.round_id) ?? null;
      currentRoundIndex = game?.rounds.findIndex((r) => r.id === data.round_id) ?? -1;
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
      currentRoundIndex = -1;
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
  $: roundLabel = game && currentRoundIndex >= 0
    ? `Runde ${currentRoundIndex + 1} / ${game.rounds.length}`
    : '–';
  $: sortedParticipants = [...participants].sort((a, b) => b.score - a.score);
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
      <button class="btn-reset" on:click={resetGame}>↺ Zurücksetzen</button>
      <button class="btn-end" on:click={endGame}>■ Spiel beenden</button>
    </header>

    <div class="layout">
      <!-- Left column: image + scores -->
      <div class="left-col">
        <div class="panel">
          <div class="panel-title">Aktuelle Runde</div>
          {#if aiImageUrl}
            <img src={aiImageUrl} alt="KI-Bild" class="round-img" />
          {:else}
            <div class="no-img">Keine Runde aktiv</div>
          {/if}
          {#if currentRound}
            <div class="round-meta">
              <span>⏱ {currentRound.time_limit}s Quizzeit</span>
              {#if currentRound.target_year}
                <span>📅 Ziel: {currentRound.target_year}</span>
              {/if}
            </div>
          {/if}
        </div>

        <div class="panel">
          <div class="panel-title">Punktestand</div>
          {#if sortedParticipants.length === 0}
            <p class="muted">Noch keine Teilnehmer</p>
          {:else}
            <div class="scores">
              {#each sortedParticipants as p, i}
                <div class="score-row">
                  <span class="rank">{i + 1}.</span>
                  <span class="pname" class:ready={p.ready}>{p.username}</span>
                  <span class="pts">{p.score} Pkt</span>
                  <button class="kick-btn" title="Spieler entfernen" on:click={() => kickParticipant(p.id)}>✕</button>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <!-- Right column: buzzer + controls -->
      <div class="right-col">
        <div class="panel">
          <div class="panel-title">Teilnehmer</div>
          {#if participants.length === 0}
            <p class="muted">Noch keine Teilnehmer</p>
          {:else}
            <div class="player-grid">
              {#each participants as p (p.id)}
                <div
                  class="player-card"
                  class:card-buzzed={getPlayerCardState(p.id) === 'buzzed'}
                  class:card-correct={getPlayerCardState(p.id) === 'correct'}
                  class:card-wrong={getPlayerCardState(p.id) === 'wrong'}
                >
                  <span>{p.username}</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Buzzer card -->
        {#if phase === 'buzzed'}
          <div class="panel buzzer-panel">
            <div class="panel-title">🔔 Buzzer</div>
            <p class="buzz-who">{buzzedParticipant?.username}</p>
            <div class="buzz-actions">
              <button class="btn-correct" on:click={correct}>
                ✓ Richtig <kbd>C</kbd>
              </button>
              <button class="btn-wrong" on:click={wrong}>
                ✗ Falsch <kbd>W</kbd>
              </button>
            </div>
          </div>
        {:else if phase === 'quiz'}
          <div class="panel quiz-panel">
            <div class="panel-title">Quiz läuft</div>
            <div class="quiz-timer">{quizTimeLeft}s</div>
          </div>
        {:else if phase === 'result'}
          <div class="panel status-panel">
            <div class="panel-title">Quiz beendet</div>
            <p class="muted">Ergebnisse angezeigt</p>
          </div>
        {:else if phase === 'revealed'}
          <div class="panel status-panel">
            <div class="panel-title">Lösung angezeigt</div>
            <p class="muted">Nächste Runde starten</p>
          </div>
        {:else if phase === 'round'}
          <div class="panel status-panel">
            <div class="panel-title">Runde läuft</div>
            <p class="muted">Warten auf Buzzer…</p>
          </div>
        {:else}
          <div class="panel status-panel">
            <div class="panel-title">Bereit</div>
            <p class="muted">Erste Runde starten</p>
          </div>
        {/if}

        <!-- Controls -->
        <div class="panel">
          <div class="panel-title">Steuerung</div>
          <div class="ctrl-grid">
            <button class="btn-primary span2" on:click={nextRound}>
              ▶ Nächste Runde <kbd>Space</kbd>
            </button>
            <button class="btn-secondary" on:click={reveal}
              disabled={!currentRound || phase === 'revealed' || phase === 'waiting'}>
              👁 Auflösen <kbd>R</kbd>
            </button>
            <button class="btn-secondary" on:click={skip}
              disabled={!currentRound || phase === 'revealed' || phase === 'waiting'}>
              ⏭ Überspringen <kbd>S</kbd>
            </button>
            <button class="btn-secondary span2" on:click={unlockAll} disabled={!currentRound}>
              🔓 Alle entsperren
            </button>
          </div>
        </div>

        <!-- Keyboard shortcuts -->
        <div class="panel shortcuts">
          <div class="panel-title">Tastenkürzel</div>
          <div class="shortcut-list">
            <div><kbd>Space</kbd><span>Nächste Runde</span></div>
            <div><kbd>C</kbd><span>Richtig</span></div>
            <div><kbd>W</kbd><span>Falsch</span></div>
            <div><kbd>R</kbd><span>Auflösen</span></div>
            <div><kbd>S</kbd><span>Überspringen</span></div>
          </div>
        </div>
      </div>
    </div>
  </div>
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

  .btn-end {
    background: #dc3545;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.45rem 0.9rem;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-end:hover { background: #c82333; }

  /* Layout */
  .layout {
    display: grid;
    grid-template-columns: 380px 1fr;
    gap: 1.25rem;
    align-items: start;
  }

  @media (max-width: 860px) {
    .layout { grid-template-columns: 1fr; }
  }

  .left-col, .right-col {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

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

  .round-img {
    width: 100%;
    aspect-ratio: 16/9;
    object-fit: cover;
    border-radius: 8px;
    display: block;
  }

  .no-img {
    width: 100%;
    aspect-ratio: 16/9;
    background: #f0f2f5;
    border-radius: 8px;
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

  /* Scores */
  .scores { display: flex; flex-direction: column; gap: 0.4rem; }
  .score-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.35rem 0;
    border-bottom: 1px solid #f0f2f5;
    font-size: 0.9rem;
  }
  .score-row:last-child { border-bottom: none; }
  .rank { color: #aaa; font-weight: 700; width: 1.5rem; }
  .pname { flex: 1; font-weight: 500; }
  .pname.ready { color: #28a745; font-weight: 700; }
  .pts { font-weight: 700; color: #0066cc; }
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

  .status-panel { background: #f8f9fa; }

  .player-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.55rem;
  }

  .player-card {
    min-height: 52px;
    border-radius: 10px;
    border: 1.5px solid #dfe3e8;
    background: #f8fafc;
    color: #1f2937;
    font-size: 0.9rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 0.5rem 0.35rem;
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    overflow-wrap: anywhere;
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

  /* Shortcuts */
  .shortcuts { background: #f8f9fa; }
  .shortcut-list {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .shortcut-list > div {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-size: 0.85rem;
    color: #555;
  }

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
