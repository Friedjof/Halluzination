<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { socket } from '$lib/socket';
  import { adminToken } from '$lib/stores/auth';
  import { api } from '$lib/api';
  import QRCode from 'qrcode';
  import type { Game } from '$lib/types';

  const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
  $: uuid = $page.params.uuid;

  let game: Game | null = null;

  type Phase = 'lobby' | 'round' | 'buzzed' | 'quiz' | 'result' | 'revealed';
  let phase: Phase = 'lobby';

  let aiImageUrl = '';
  let originalUrl = '';
  let solutionText = '';
  let targetYear: number | null = null;

  let buzzerName = '';

  let quizTimeLeft = 0;
  let quizTimer: ReturnType<typeof setInterval> | null = null;

  let leaderboard: { participant_id: number; username: string; score: number }[] = [];

  // Live participant list shown during lobby
  let lobbyParticipants: { id: number; username: string; ready: boolean }[] = [];

  let qrCanvas: HTMLCanvasElement;
  $: if (qrCanvas && game?.join_url) {
    QRCode.toCanvas(qrCanvas, game.join_url, { width: 300, margin: 2 }).catch(() => {});
  }

  function resolveUrl(url: string): string {
    return url.startsWith('http') ? url : `${BACKEND}${url}`;
  }

  onMount(async () => {
    // Load game title (admin token available via shared localStorage)
    try {
      game = await api.get(`/api/games/${uuid}`);
      lobbyParticipants = (game?.participants ?? []).map((p) => ({ id: p.id, username: p.username, ready: false }));
    } catch {}

    socket.connect();
    socket.emit('join_present', { game_uuid: uuid });

    socket.on('round_start', (data) => {
      aiImageUrl = resolveUrl(data.ai_image_url);
      originalUrl = '';
      solutionText = '';
      targetYear = null;
      buzzerName = '';
      phase = 'round';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('lockout', (data) => {
      if (data.winner_name) {
        buzzerName = data.winner_name;
        phase = 'buzzed';
      } else if (data.reason === 'wrong') {
        buzzerName = '';
        phase = 'round';
      }
    });

    socket.on('unlock', () => {
      if (phase === 'buzzed') { buzzerName = ''; phase = 'round'; }
    });

    socket.on('unlock_all', () => {
      if (phase === 'buzzed') { buzzerName = ''; phase = 'round'; }
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
      leaderboard = data.leaderboard;
      phase = 'result';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('round_end', (data) => {
      originalUrl = resolveUrl(data.original_url);
      aiImageUrl = resolveUrl(data.ai_url);
      solutionText = data.solution_text;
      targetYear = data.target_year ?? null;
      buzzerName = '';
      phase = 'revealed';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('participants_update', (data: { participants: { id: number; username: string; ready: boolean }[] }) => {
      lobbyParticipants = data.participants;
    });

    socket.on('game_end', () => {
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
      window.close();
    });
  });

  onDestroy(() => {
    if (quizTimer) clearInterval(quizTimer);
    socket.off('round_start');
    socket.off('lockout');
    socket.off('unlock');
    socket.off('unlock_all');
    socket.off('quiz_start');
    socket.off('quiz_result');
    socket.off('round_end');
    socket.off('participants_update');
    socket.off('game_end');
    socket.disconnect();
  });
</script>

<div class="screen">
  {#if game}
    <div class="game-title">{game.title}</div>
  {/if}

  {#if phase === 'lobby'}
    <div class="lobby">
      <p class="lobby-hint">Scanne den QR-Code oder öffne den Link</p>
      <canvas bind:this={qrCanvas} class="qr"></canvas>
      {#if game?.join_url}
        <code class="lobby-url">{game.join_url}</code>
      {/if}

      <div class="player-list">
        {#if lobbyParticipants.length === 0}
          <p class="player-list-empty">Noch keine Teilnehmer…</p>
        {:else}
          <p class="player-list-label">Bereit ({lobbyParticipants.length})</p>
          <div class="player-chips">
            {#each lobbyParticipants as p (p.id)}
              <span class="player-chip">{p.username}</span>
            {/each}
          </div>
        {/if}
      </div>
    </div>

  {:else if phase === 'round' || phase === 'buzzed' || phase === 'quiz'}
    <div class="image-area">
      {#if aiImageUrl}
        <img src={aiImageUrl} alt="KI-Bild" class:blurred={phase === 'quiz'} />
      {/if}

      {#if phase === 'buzzed'}
        <div class="overlay buzzer-overlay">
          <span class="buzz-icon">🔔</span>
          <span class="buzz-name">{buzzerName}</span>
        </div>
      {/if}

      {#if phase === 'quiz'}
        <div class="timer-badge">
          <span class="timer-num">{quizTimeLeft}</span>
          <span class="timer-label">Sekunden</span>
        </div>
      {/if}
    </div>

  {:else if phase === 'result'}
    <div class="result-area">
      <h2>Zwischenergebnis</h2>
      <div class="leaderboard">
        {#each leaderboard as p, i}
          <div class="lb-row">
            <span class="lb-rank">#{i + 1}</span>
            <span class="lb-name">{p.username}</span>
            <span class="lb-score">{p.score} Pkt</span>
          </div>
        {/each}
      </div>
    </div>

  {:else if phase === 'revealed'}
    <div class="reveal-area">
      <div class="images-compare">
        <div class="img-col">
          <span class="img-label">KI-Version</span>
          <img src={aiImageUrl} alt="KI" />
        </div>
        <div class="img-col">
          <span class="img-label">Original</span>
          <img src={originalUrl} alt="Original" />
        </div>
      </div>
      {#if solutionText || targetYear}
        <div class="solution">
          {#if solutionText}<p>{solutionText}</p>{/if}
          {#if targetYear}<p class="year">📅 {targetYear}</p>{/if}
        </div>
      {/if}
    </div>

  {/if}
</div>

<style>
  :global(body) { margin: 0; background: #0a0a1a; }

  .screen {
    width: 100vw;
    min-height: 100vh;
    background: #0a0a1a;
    color: white;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.75rem 1rem;
    box-sizing: border-box;
    font-family: system-ui, sans-serif;
  }

  .game-title {
    font-size: 1rem;
    font-weight: 700;
    color: rgba(255,255,255,0.4);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
  }

  /* Lobby */
  .lobby {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1.25rem;
  }

  .lobby-hint {
    font-size: 1rem;
    color: rgba(255,255,255,0.5);
    margin: 0;
    letter-spacing: 0.3px;
  }

  .qr {
    border-radius: 16px;
    border: 6px solid white;
    box-shadow: 0 8px 48px rgba(0,0,0,0.6);
    display: block;
  }

  .lobby-url {
    font-size: 1.05rem;
    color: rgba(255,255,255,0.7);
    background: rgba(255,255,255,0.08);
    padding: 0.5rem 1rem;
    border-radius: 8px;
    word-break: break-all;
    text-align: center;
    max-width: 500px;
  }

  .lobby-waiting {
    font-size: 0.85rem;
    color: rgba(255,255,255,0.3);
    margin: 0;
  }

  .player-list {
    text-align: center;
    max-width: 600px;
    width: 100%;
  }

  .player-list-empty {
    font-size: 0.9rem;
    color: rgba(255,255,255,0.25);
    margin: 0;
  }

  .player-list-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 0 0 0.6rem;
  }

  .player-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: center;
  }

  .player-chip {
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 20px;
    padding: 0.3rem 0.85rem;
    font-size: 1rem;
    font-weight: 600;
    color: white;
    animation: pop-in 0.25s ease;
  }

  @keyframes pop-in {
    from { transform: scale(0.6); opacity: 0; }
    to   { transform: scale(1);   opacity: 1; }
  }

  /* Image area */
  .image-area {
    position: relative;
    width: min(100%, calc((100vh - 5rem) * 16 / 9));
    aspect-ratio: 16 / 9;
    border-radius: 16px;
    overflow: hidden;
    background: #111;
    box-shadow: 0 8px 48px rgba(0,0,0,0.7);
  }

  .image-area img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: filter 0.5s ease;
  }

  .image-area img.blurred {
    filter: blur(14px) brightness(0.6);
  }

  .overlay {
    position: absolute;
    inset: 0;
  }

  .buzzer-overlay {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.5);
    gap: 0.5rem;
  }

  .buzz-icon { font-size: 4rem; }
  .buzz-name {
    font-size: 3rem;
    font-weight: 900;
    color: #ffd700;
    text-shadow: 0 2px 16px rgba(0,0,0,0.9);
    text-align: center;
    padding: 0 1rem;
  }

  .timer-badge {
    position: absolute;
    top: 1.25rem;
    right: 1.25rem;
    background: rgba(0,0,0,0.75);
    border-radius: 14px;
    padding: 0.75rem 1.5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    backdrop-filter: blur(4px);
  }
  .timer-num { font-size: 2.8rem; font-weight: 900; line-height: 1; }
  .timer-label { font-size: 0.65rem; color: rgba(255,255,255,0.55); text-transform: uppercase; letter-spacing: 1px; }

  /* Result / leaderboard */
  .result-area {
    width: 100%;
    max-width: 680px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
  }

  h2 { font-size: 2.2rem; font-weight: 900; margin: 0; }

  .leaderboard {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .lb-row {
    display: flex;
    align-items: center;
    background: rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 0.85rem 1.25rem;
    gap: 1rem;
    font-size: 1.15rem;
  }
  .lb-row.winner { background: rgba(255,215,0,0.18); border: 1px solid rgba(255,215,0,0.35); }
  .lb-rank { font-weight: 700; color: rgba(255,255,255,0.45); width: 2.5rem; }
  .lb-name { flex: 1; font-weight: 600; }
  .lb-score { font-weight: 800; color: #60d394; font-size: 1.05rem; }

  /* Reveal */
  .reveal-area {
    width: 100%;
    max-width: min(100vw, 1400px);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.25rem;
  }

  .images-compare {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    width: 100%;
  }

  .img-col {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .img-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: rgba(255,255,255,0.45);
    text-transform: uppercase;
    letter-spacing: 0.6px;
    text-align: center;
  }

  .img-col img {
    width: 100%;
    aspect-ratio: 16/9;
    object-fit: cover;
    border-radius: 12px;
  }

  .solution {
    text-align: center;
    font-size: 1.1rem;
    color: rgba(255,255,255,0.85);
    max-width: 700px;
    line-height: 1.55;
  }

  .year { font-size: 1.4rem; font-weight: 800; color: #ffd700; margin-top: 0.25rem; }
</style>
