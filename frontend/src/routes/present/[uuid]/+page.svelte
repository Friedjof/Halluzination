<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { socket } from '$lib/socket';
  import { adminToken } from '$lib/stores/auth';
  import { api } from '$lib/api';
  import QRCode from 'qrcode';
  import type { Game } from '$lib/types';
  import ImageCompareSlider from '$lib/components/ImageCompareSlider.svelte';

  const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
  $: uuid = $page.params.uuid;

  let game: Game | null = null;

  type Phase = 'lobby' | 'round' | 'buzzed' | 'quiz' | 'result' | 'revealed' | 'final';
  let phase: Phase = 'lobby';

  let aiImageUrl = '';
  let originalUrl = '';
  let solutionText = '';
  let targetYear: number | null = null;
  let correctLocation = '';

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

  function getRank(lb: { score: number }[], index: number): number {
    return lb.filter(p => p.score > lb[index].score).length + 1;
  }

  function rankLabel(lb: { score: number }[], index: number): string {
    const r = getRank(lb, index);
    if (r === 1) return '🥇';
    if (r === 2) return '🥈';
    if (r === 3) return '🥉';
    return `#${r}`;
  }

  function resolveUrl(url: string | null | undefined): string {
    if (!url) return '';
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
      correctLocation = '';
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
      originalUrl = resolveUrl(data.original_url);
      aiImageUrl = resolveUrl(data.ai_url);
      solutionText = data.solution_text ?? '';
      targetYear = data.target_year ?? null;
      correctLocation = data.correct_location ?? '';
      phase = 'revealed';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('round_end', (data) => {
      originalUrl = resolveUrl(data.original_url);
      aiImageUrl = resolveUrl(data.ai_url);
      solutionText = data.solution_text;
      targetYear = data.target_year ?? null;
      correctLocation = data.correct_location ?? '';
      buzzerName = '';
      phase = 'revealed';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('participants_update', (data: { participants: { id: number; username: string; ready: boolean }[] }) => {
      lobbyParticipants = data.participants;
    });

    socket.on('game_reset', () => {
      aiImageUrl = '';
      originalUrl = '';
      solutionText = '';
      targetYear = null;
      correctLocation = '';
      buzzerName = '';
      leaderboard = [];
      quizTimeLeft = 0;
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
      lobbyParticipants = lobbyParticipants.map((p) => ({ ...p, ready: false }));
      phase = 'lobby';
    });

    socket.on('game_end', (data) => {
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
      if (data?.leaderboard?.length) leaderboard = data.leaderboard;
      phase = 'final';
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
    socket.off('game_reset');
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
          <p class="player-list-label">
            Bereit ({lobbyParticipants.filter((p) => p.ready).length}/{lobbyParticipants.length})
          </p>
          <div class="player-chips">
            {#each lobbyParticipants as p (p.id)}
              <span class="player-chip" class:ready={p.ready}>
                {#if p.ready}✓ {/if}{p.username}
              </span>
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
        <div class="buzz-top-badge">
          <span class="buzz-label">Buzzer</span>
          <span class="buzz-name">{buzzerName}</span>
        </div>
      {/if}

      {#if phase === 'quiz'}
        <div class="quiz-hint">
          Schnell: Schau auf dein Handy und beantworte das Quiz.
        </div>
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
            <span class="lb-rank">#{getRank(leaderboard, i)}</span>
            <span class="lb-name">{p.username}</span>
            <span class="lb-score">{p.score} Pkt</span>
          </div>
        {/each}
      </div>
    </div>

  {:else if phase === 'revealed'}
    <div class="reveal-area">
      <ImageCompareSlider aiUrl={aiImageUrl} originalUrl={originalUrl} />
      {#if solutionText || targetYear || correctLocation}
        <div class="solution">
          {#if solutionText}<p>{solutionText}</p>{/if}
          {#if correctLocation}<p>📍 Richtige Location: <strong>{correctLocation}</strong></p>{/if}
          {#if targetYear}<p class="year">📅 {targetYear}</p>{/if}
        </div>
      {/if}
    </div>

  {:else if phase === 'final'}
    <div class="final-area">
      <h2 class="final-title">🏆 Endstand</h2>
      <div class="final-bars">
        {#each leaderboard as p, i}
          {@const maxScore = leaderboard[0]?.score || 1}
          {@const pct = Math.max(6, (p.score / maxScore) * 100)}
          <div class="bar-row" style="animation-delay: {i * 80}ms">
            <span class="bar-rank">{rankLabel(leaderboard, i)}</span>
            <span class="bar-name">{p.username}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                class:gold={getRank(leaderboard, i) === 1}
                class:silver={getRank(leaderboard, i) === 2}
                class:bronze={getRank(leaderboard, i) === 3}
                style="width: {pct}%"
              ></div>
            </div>
            <span class="bar-score">{p.score} Pkt</span>
          </div>
        {/each}
      </div>
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
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }

  .player-chip.ready {
    background: rgba(34, 197, 94, 0.18);
    border-color: rgba(34, 197, 94, 0.6);
    color: #c8facc;
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

  .buzz-top-badge {
    position: absolute;
    top: 1rem;
    left: 50%;
    transform: translateX(-50%);
    max-width: min(88%, 680px);
    padding: 0.55rem 1rem 0.65rem;
    border-radius: 12px;
    background: rgba(0,0,0,0.62);
    border: 1px solid rgba(255,255,255,0.22);
    backdrop-filter: blur(3px);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.05rem;
    text-align: center;
  }

  .buzz-label {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.62);
  }

  .buzz-name {
    font-size: clamp(1rem, 2.1vw, 1.55rem);
    font-weight: 800;
    color: #ffd700;
    text-shadow: 0 2px 16px rgba(0,0,0,0.9);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
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

  .quiz-hint {
    position: absolute;
    left: 50%;
    bottom: 1rem;
    transform: translateX(-50%);
    width: min(92%, 980px);
    text-align: center;
    font-size: clamp(1rem, 1.8vw, 1.5rem);
    font-weight: 800;
    color: #ffffff;
    background: rgba(0,0,0,0.62);
    border: 1px solid rgba(255,255,255,0.24);
    border-radius: 12px;
    padding: 0.6rem 1rem;
    backdrop-filter: blur(3px);
    text-shadow: 0 2px 14px rgba(0,0,0,0.85);
  }

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

  .solution {
    text-align: center;
    font-size: 1.1rem;
    color: rgba(255,255,255,0.85);
    max-width: 700px;
    line-height: 1.55;
  }

  .year { font-size: 1.4rem; font-weight: 800; color: #ffd700; margin-top: 0.25rem; }

  /* Final leaderboard */
  .final-area {
    width: 100%;
    max-width: min(100vw, 1100px);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2rem;
    padding: 0 1rem;
    box-sizing: border-box;
  }

  .final-title {
    font-size: clamp(2rem, 4vw, 3.2rem);
    font-weight: 900;
    margin: 0;
    letter-spacing: -0.5px;
  }

  .final-bars {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .bar-row {
    display: grid;
    grid-template-columns: 3rem 14rem 1fr 6rem;
    align-items: center;
    gap: 1rem;
    opacity: 0;
    animation: bar-in 0.4s ease forwards;
  }

  @keyframes bar-in {
    from { opacity: 0; transform: translateX(-20px); }
    to   { opacity: 1; transform: translateX(0); }
  }

  .bar-rank {
    font-size: clamp(1.1rem, 2vw, 1.6rem);
    text-align: center;
  }

  .bar-name {
    font-size: clamp(1rem, 1.8vw, 1.4rem);
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .bar-track {
    background: rgba(255,255,255,0.1);
    border-radius: 8px;
    height: clamp(28px, 3.5vw, 48px);
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    border-radius: 8px;
    background: rgba(255,255,255,0.5);
    transition: width 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .bar-fill.gold   { background: linear-gradient(90deg, #f59e0b, #fde68a); }
  .bar-fill.silver { background: linear-gradient(90deg, #94a3b8, #e2e8f0); }
  .bar-fill.bronze { background: linear-gradient(90deg, #b45309, #fcd34d); }

  .bar-score {
    font-size: clamp(0.95rem, 1.6vw, 1.3rem);
    font-weight: 800;
    color: rgba(255,255,255,0.75);
    text-align: right;
    white-space: nowrap;
  }
</style>
