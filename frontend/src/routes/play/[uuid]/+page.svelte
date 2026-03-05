<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { socket } from '$lib/socket';

  const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
  $: uuid = $page.params.uuid;

  type Phase =
    | 'join' | 'lobby' | 'waiting' | 'waiting_next' | 'buzzed'
    | 'other_buzzed' | 'locked' | 'quiz' | 'quiz_done'
    | 'result' | 'ended' | 'kicked';

  let phase: Phase = 'join';

  // Participant
  let participantId: number | null = null;
  let username = '';
  let nameInput = '';
  let joinError = '';
  let joining = false;

  // Cookie-based session persistence
  function getCookie(key: string): string | null {
    const m = document.cookie.match(new RegExp('(?:^|; )' + key + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
  }
  function setCookie(key: string, value: string, days = 7) {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${key}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
  }
  function saveSession(kicked = false) {
    setCookie(`halluz_${uuid}`, JSON.stringify({ participant_id: participantId, username, kicked }));
  }

  // Round
  let currentRoundId: number | null = null;

  // Buzzer
  let buzzerWinner = '';

  // Quiz
  type Loc = { id: number; name: string };
  let quizLocations: Loc[] = [];
  let quizTimeLimit = 0;
  let quizTimeLeft = 0;
  let selectedLocationId: number | null = null;
  let yearGuess = '';
  let quizTimer: ReturnType<typeof setInterval> | null = null;
  let quizSubmitted = false;
  let lobbyReady = false;

  // Connection state
  let disconnected = false;

  // Sound
  function playBuzzer() {
    const audio = new Audio('/buzzer.mp3');
    audio.play().catch(() => {});
  }

  // Result
  let myPoints = 0;
  let myScore = 0;
  let myLocationCorrect = false;
  let targetYear: number | null = null;
  let correctLocation = '';
  let leaderboard: { username: string; score: number }[] = [];

  async function joinGame() {
    if (!nameInput.trim()) return;
    joining = true;
    joinError = '';
    try {
      const res = await fetch(`${BASE}/api/games/${uuid}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: nameInput.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Fehler' }));
        throw new Error(err.detail ?? 'Fehler beim Beitreten');
      }
      const data = await res.json();
      participantId = data.participant_id;
      username = data.username;
      saveSession(false);

      socket.connect();
      socket.emit('join_game', { game_uuid: uuid, participant_id: participantId });
      phase = 'lobby';
    } catch (e: any) {
      joinError = e.message;
    } finally {
      joining = false;
    }
  }

  function signalReady() {
    if (lobbyReady || !participantId) return;
    lobbyReady = true;
    socket.emit('lobby_ready', { game_uuid: uuid, participant_id: participantId });
  }

  function buzz() {
    if (phase !== 'waiting' || !participantId || !currentRoundId) return;
    socket.emit('buzz', { game_uuid: uuid, participant_id: participantId, round_id: currentRoundId });
  }

  function submitQuiz() {
    if (!participantId || !currentRoundId || quizSubmitted) return;
    quizSubmitted = true;
    socket.emit('quiz_answer', {
      game_uuid: uuid,
      round_id: currentRoundId,
      participant_id: participantId,
      location_id: selectedLocationId ?? undefined,
      year_guess: yearGuess ? parseInt(yearGuess) : undefined,
    });
    phase = 'quiz_done';
    if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
  }

  onMount(() => {
    socket.on('connect', () => { disconnected = false; });
    socket.on('disconnect', () => { disconnected = true; });

    socket.on('joined', (data) => {
      if (data.current_round_id) {
        currentRoundId = data.current_round_id;
        phase = data.locked ? 'locked' : 'waiting';
      } else {
        phase = 'lobby';
      }
    });

    socket.on('round_start', (data) => {
      currentRoundId = data.round_id;
      buzzerWinner = '';
      selectedLocationId = null;
      yearGuess = '';
      quizSubmitted = false;
      correctLocation = '';
      phase = 'waiting';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('buzz_confirmed', () => {
      playBuzzer();
      phase = 'buzzed';
    });

    socket.on('lockout', (data) => {
      if (data.winner_name) {
        buzzerWinner = data.winner_name;
        if (phase !== 'locked') {
          phase = 'other_buzzed';
        }
      } else if (data.reason === 'wrong') {
        phase = 'locked';
      }
    });

    socket.on('unlock', () => {
      if (phase === 'other_buzzed' || phase === 'locked') phase = 'waiting';
    });

    socket.on('unlock_all', () => {
      if (phase === 'other_buzzed' || phase === 'locked' || phase === 'buzzed') {
        phase = 'waiting';
      }
    });

    socket.on('participants_update', (data: { participants: { id: number; locked?: boolean }[] }) => {
      const me = data.participants.find((p) => p.id === participantId);
      if (!me) return;
      if (me.locked) {
        if (phase === 'waiting' || phase === 'other_buzzed' || phase === 'locked') {
          phase = 'locked';
        }
      } else if (phase === 'locked') {
        phase = 'waiting';
      }
    });

    socket.on('quiz_start', (data) => {
      quizLocations = data.locations;
      quizTimeLimit = data.time_limit;
      quizTimeLeft = data.time_limit;
      selectedLocationId = null;
      yearGuess = '';
      quizSubmitted = false;
      phase = 'quiz';
      if (quizTimer) clearInterval(quizTimer);
      quizTimer = setInterval(() => {
        quizTimeLeft = Math.max(0, quizTimeLeft - 1);
        if (quizTimeLeft === 0) {
          clearInterval(quizTimer!);
          quizTimer = null;
          if (phase === 'quiz') submitQuiz();
        }
      }, 1000);
    });

    socket.on('quiz_result', (data) => {
      leaderboard = data.leaderboard;
      targetYear = data.target_year ?? null;
      correctLocation = data.correct_location ?? '';
      const me = data.results.find((r: any) => r.participant_id === participantId);
      if (me) {
        myPoints = me.points_awarded;
        myScore = me.score;
        myLocationCorrect = me.location_correct;
      } else {
        myPoints = 0;
        myScore = 0;
        myLocationCorrect = false;
      }
      phase = 'result';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('round_end', () => {
      if (phase !== 'result') phase = 'waiting_next';
    });

    socket.on('game_end', (data) => {
      if (data?.leaderboard?.length) leaderboard = data.leaderboard;
      phase = 'ended';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
    });

    socket.on('game_reset', () => {
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
      lobbyReady = false;
      phase = 'lobby';
    });

    socket.on('kicked', () => {
      saveSession(true);
      phase = 'kicked';
      if (quizTimer) { clearInterval(quizTimer); quizTimer = null; }
      socket.disconnect();
    });

    // Auto-reconnect from cookie
    const raw = getCookie(`halluz_${uuid}`);
    if (raw) {
      try {
        const session = JSON.parse(raw);
        if (session.kicked) {
          phase = 'kicked';
        } else if (session.participant_id && session.username) {
          participantId = session.participant_id;
          username = session.username;
          socket.connect();
          socket.emit('join_game', { game_uuid: uuid, participant_id: participantId });
          // phase will be set by 'joined' or 'kicked' event handler
        }
      } catch {}
    }
  });

  onDestroy(() => {
    if (quizTimer) clearInterval(quizTimer);
    socket.off('connect');
    socket.off('disconnect');
    socket.off('joined');
    socket.off('round_start');
    socket.off('buzz_confirmed');
    socket.off('lockout');
    socket.off('unlock');
    socket.off('unlock_all');
    socket.off('participants_update');
    socket.off('quiz_start');
    socket.off('quiz_result');
    socket.off('round_end');
    socket.off('game_reset');
    socket.off('game_end');
    socket.off('kicked');
    socket.disconnect();
  });

  $: quizPct = quizTimeLimit > 0 ? (quizTimeLeft / quizTimeLimit) * 100 : 100;
</script>

<div class="screen">

  {#if disconnected}
    <div class="disconnect-banner">⚠ Verbindung unterbrochen – wird wiederhergestellt…</div>
  {/if}

  {#if phase !== 'join' && username}
    <div class="username-badge">{username}</div>
  {/if}

  <!-- ── JOIN ── -->
  {#if phase === 'join'}
    <div class="card">
      <h1 class="app-name">Halluzination</h1>
      <p class="sub">Wie möchtest du heißen?</p>
      <form on:submit|preventDefault={joinGame} class="join-form">
        <input
          type="text"
          bind:value={nameInput}
          placeholder="Dein Name…"
          maxlength="24"
          autocomplete="off"
          autofocus
          required
        />
        {#if joinError}<p class="err">{joinError}</p>{/if}
        <button type="submit" class="btn-join" disabled={joining || !nameInput.trim()}>
          {joining ? 'Beitreten…' : 'Mitspielen →'}
        </button>
      </form>
    </div>

  <!-- ── LOBBY ── -->
  {:else if phase === 'lobby'}
    <div class="lobby-ready-screen">
      <p class="hi">Hallo, <strong>{username}</strong>!</p>
      {#if lobbyReady}
        <div class="card center ready-card">
          <span class="big-emoji">✅</span>
          <p class="state-title">Bereit!</p>
          <p class="hint">Warte auf die anderen…</p>
        </div>
      {:else}
        <p class="ready-hint">Drücke den Buzzer um zu bestätigen, dass du bereit bist</p>
        <button class="buzzer-btn ready-buzzer" on:click={signalReady} on:touchstart|preventDefault={signalReady}>
          BEREIT!
        </button>
      {/if}
    </div>

  <!-- ── WAITING (buzzer ready) ── -->
  {:else if phase === 'waiting'}
    <div class="buzzer-screen">
      <p class="round-hint">Runde läuft – wer weiß es?</p>
      <button class="buzzer-btn" on:click={buzz} on:touchstart|preventDefault={buzz}>
        BUZZ!
      </button>
    </div>

  <!-- ── BUZZED (I won) ── -->
  {:else if phase === 'buzzed'}
    <div class="buzzer-screen">
      <p class="round-hint">Du hast gebuzzert</p>
      <button class="buzzer-btn locked" disabled>BUZZ!</button>
      <p class="state-title">Du bist dran!</p>
      <p class="hint">Der Spielleiter entscheidet…</p>
    </div>

  <!-- ── OTHER BUZZED ── -->
  {:else if phase === 'other_buzzed'}
    <div class="buzzer-screen">
      <p class="round-hint"><strong>{buzzerWinner}</strong> hat gebuzzert</p>
      <button class="buzzer-btn locked" disabled>BUZZ!</button>
      <p class="hint">Warte auf die Entscheidung des Spielleiters</p>
    </div>

  <!-- ── LOCKED ── -->
  {:else if phase === 'locked'}
    <div class="buzzer-screen">
      <p class="round-hint">Falsch gebuzzert</p>
      <button class="buzzer-btn locked" disabled>BUZZ!</button>
      <p class="hint">Für diese Runde gesperrt</p>
    </div>

  <!-- ── QUIZ ── -->
  {:else if phase === 'quiz'}
    <div class="quiz-screen">
      <div class="timer-bar">
        <div class="timer-fill" style="width: {quizPct}%; background: {quizPct < 30 ? '#dc3545' : '#28a745'}"></div>
        <span class="timer-text">{quizTimeLeft}s</span>
      </div>

      <p class="quiz-q">Wo wurde das Foto aufgenommen?</p>
      <div class="locations">
        {#each quizLocations as loc}
          <button
            class="loc-btn"
            class:selected={selectedLocationId === loc.id}
            on:click={() => selectedLocationId = selectedLocationId === loc.id ? null : loc.id}
          >
            {loc.name}
          </button>
        {/each}
      </div>

      <p class="quiz-q">Aufnahmejahr (ca.)?</p>
      <input
        class="year-input"
        type="number"
        bind:value={yearGuess}
        placeholder="z. B. 1987"
        min="1800"
        max="2030"
      />

      <button class="btn-submit" on:click={submitQuiz}>
        Antwort absenden
      </button>
    </div>

  <!-- ── QUIZ DONE ── -->
  {:else if phase === 'quiz_done'}
    <div class="card center">
      <span class="big-emoji">✅</span>
      <p class="state-title">Antwort gesendet</p>
      <p class="hint">Warte auf die Auswertung…</p>
    </div>

  <!-- ── RESULT ── -->
  {:else if phase === 'result'}
    <div class="result-screen">
      <div class="my-result" class:good={myPoints > 0}>
        <span class="pts-num">{myPoints > 0 ? '+' : ''}{myPoints}</span>
        <span class="pts-label">Punkte diese Runde</span>
        <span class="total-score">Gesamt: {myScore} Punkte</span>
        {#if correctLocation}
          <span class="correct-loc" class:good={myLocationCorrect}>
            📍 {correctLocation}{myLocationCorrect ? ' ✓' : ''}
          </span>
        {/if}
        {#if targetYear}
          <span class="target-year">📅 Richtiges Jahr: {targetYear}</span>
        {/if}
      </div>

      <div class="lb-section">
        <p class="lb-title">Rangliste</p>
        {#each leaderboard as p, i}
          <div class="lb-row" class:me={p.username === username}>
            <span class="lb-rank">{i + 1}.</span>
            <span class="lb-name">{p.username}</span>
            <span class="lb-score">{p.score} Pkt</span>
          </div>
        {/each}
      </div>
    </div>

  <!-- ── KICKED ── -->
  {:else if phase === 'kicked'}
    <div class="card center">
      <span class="big-emoji">🚫</span>
      <p class="state-title">Entfernt</p>
      <p class="hint">Du wurdest vom Spielleiter aus dem Spiel entfernt.</p>
    </div>

  <!-- ── WAITING NEXT ROUND ── -->
  {:else if phase === 'waiting_next'}
    <div class="card center">
      <span class="big-emoji">⏳</span>
      <p class="state-title">Runde vorbei</p>
      <p class="hint">Warte auf die nächste Runde…</p>
    </div>

  <!-- ── ENDED ── -->
  {:else if phase === 'ended'}
    <div class="result-screen">
      <p class="state-title" style="text-align:center;margin-bottom:1rem;">🏆 Spiel beendet!</p>
      <div class="lb-section">
        <p class="lb-title">Endstand</p>
        {#each leaderboard as p, i}
          <div class="lb-row" class:me={p.username === username} class:winner={i === 0}>
            <span class="lb-rank">{i + 1}.</span>
            <span class="lb-name">{p.username}</span>
            <span class="lb-score">{p.score} Pkt</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

</div>

<style>
  :global(html, body) {
    margin: 0;
    padding: 0;
    background: #0f0f1a;
    min-height: 100vh;
    font-family: system-ui, sans-serif;
    color: white;
    -webkit-tap-highlight-color: transparent;
  }

  .screen {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 1.5rem 1rem;
    box-sizing: border-box;
  }

  /* Card (centered content) */
  .card {
    background: rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 2rem 1.5rem;
    width: 100%;
    max-width: 400px;
    box-sizing: border-box;
  }

  .card.center {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 0.5rem;
  }

  /* Join */
  .app-name {
    font-size: 1.6rem;
    font-weight: 900;
    margin: 0 0 0.25rem;
    text-align: center;
    letter-spacing: -0.5px;
  }

  .sub {
    font-size: 1rem;
    color: rgba(255,255,255,0.6);
    text-align: center;
    margin: 0 0 1.5rem;
  }

  .join-form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  input[type="text"] {
    background: rgba(255,255,255,0.1);
    border: 1.5px solid rgba(255,255,255,0.2);
    border-radius: 12px;
    color: white;
    font-size: 1.1rem;
    padding: 0.85rem 1rem;
    outline: none;
    width: 100%;
    box-sizing: border-box;
  }
  input[type="text"]::placeholder { color: rgba(255,255,255,0.35); }
  input[type="text"]:focus { border-color: rgba(255,255,255,0.5); }

  .err {
    color: #ff6b6b;
    font-size: 0.85rem;
    text-align: center;
    margin: 0;
  }

  .btn-join {
    background: white;
    color: #0f0f1a;
    border: none;
    border-radius: 12px;
    padding: 0.9rem;
    font-size: 1rem;
    font-weight: 800;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .btn-join:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-join:not(:disabled):active { opacity: 0.8; }

  /* Lobby / states */
  .big-emoji { font-size: 3.5rem; line-height: 1; }
  .hi { font-size: 1.15rem; margin: 0; color: rgba(255,255,255,0.85); }
  .state-title { font-size: 1.4rem; font-weight: 800; margin: 0; }
  .hint { font-size: 0.9rem; color: rgba(255,255,255,0.5); margin: 0; }

  /* Gold pulse for buzzed winner */
  .pulse-gold {
    border: 2px solid #ffd700;
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(255,215,0,0.4); }
    50%       { box-shadow: 0 0 0 16px rgba(255,215,0,0); }
  }

  /* Buzzer screen */
  .buzzer-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2rem;
    width: 100%;
  }

  /* Lobby ready */
  .lobby-ready-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.75rem;
    width: 100%;
  }

  .ready-hint {
    font-size: 0.9rem;
    color: rgba(255,255,255,0.5);
    text-align: center;
    margin: 0;
    max-width: 280px;
  }

  .ready-buzzer {
    background: radial-gradient(circle at 35% 35%, #44cc66, #228833) !important;
    box-shadow:
      0 8px 0 #115522,
      0 12px 32px rgba(40,160,80,0.5) !important;
  }

  .ready-card { border: 2px solid #28a745; }

  .round-hint {
    font-size: 0.9rem;
    color: rgba(255,255,255,0.5);
    margin: 0;
  }

  .buzzer-btn {
    width: min(75vw, 280px);
    height: min(75vw, 280px);
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #ff4444, #cc0000);
    border: 6px solid rgba(255,255,255,0.15);
    color: white;
    font-size: clamp(1.8rem, 8vw, 2.8rem);
    font-weight: 900;
    letter-spacing: 2px;
    cursor: pointer;
    box-shadow:
      0 8px 0 #880000,
      0 12px 32px rgba(200,0,0,0.5);
    transition: transform 0.08s, box-shadow 0.08s;
    user-select: none;
    touch-action: none;
  }

  .buzzer-btn.locked,
  .buzzer-btn:disabled {
    background: radial-gradient(circle at 35% 35%, #9ca3af, #6b7280);
    box-shadow:
      0 8px 0 #4b5563,
      0 12px 28px rgba(0,0,0,0.35);
    cursor: not-allowed;
    opacity: 0.95;
    transform: none;
  }

  .buzzer-btn:active {
    transform: translateY(6px);
    box-shadow:
      0 2px 0 #880000,
      0 4px 16px rgba(200,0,0,0.4);
  }

  .buzzer-btn.locked:active,
  .buzzer-btn:disabled:active {
    transform: none;
    box-shadow:
      0 8px 0 #4b5563,
      0 12px 28px rgba(0,0,0,0.35);
  }

  /* Quiz */
  .quiz-screen {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: 100%;
    max-width: 440px;
    padding-top: 0.5rem;
  }

  .timer-bar {
    position: relative;
    height: 36px;
    background: rgba(255,255,255,0.1);
    border-radius: 10px;
    overflow: hidden;
  }

  .timer-fill {
    height: 100%;
    border-radius: 10px;
    transition: width 1s linear, background 0.3s;
  }

  .timer-text {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    font-weight: 700;
  }

  .quiz-q {
    font-size: 0.95rem;
    font-weight: 600;
    color: rgba(255,255,255,0.75);
    margin: 0.25rem 0 0;
  }

  .locations {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .loc-btn {
    background: rgba(255,255,255,0.08);
    border: 2px solid rgba(255,255,255,0.12);
    border-radius: 12px;
    color: white;
    font-size: 1rem;
    font-weight: 600;
    padding: 0.85rem 1rem;
    cursor: pointer;
    text-align: left;
    transition: background 0.12s, border-color 0.12s;
  }
  .loc-btn:active { opacity: 0.8; }
  .loc-btn.selected {
    background: rgba(0,102,204,0.35);
    border-color: #0099ff;
  }

  .year-input {
    background: rgba(255,255,255,0.1);
    border: 1.5px solid rgba(255,255,255,0.2);
    border-radius: 12px;
    color: white;
    font-size: 1.1rem;
    padding: 0.8rem 1rem;
    outline: none;
    width: 100%;
    box-sizing: border-box;
    -moz-appearance: textfield;
  }
  .year-input::-webkit-outer-spin-button,
  .year-input::-webkit-inner-spin-button { -webkit-appearance: none; }
  .year-input::placeholder { color: rgba(255,255,255,0.35); }
  .year-input:focus { border-color: rgba(255,255,255,0.5); }

  .btn-submit {
    background: #0066cc;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 0.9rem;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    margin-top: 0.25rem;
  }
  .btn-submit:active { opacity: 0.85; }

  /* Result */
  .result-screen {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    width: 100%;
    max-width: 400px;
  }

  .my-result {
    background: rgba(255,255,255,0.06);
    border-radius: 18px;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.3rem;
    border: 2px solid rgba(255,255,255,0.1);
  }
  .my-result.good { border-color: #28a745; background: rgba(40,167,69,0.15); }

  .pts-num {
    font-size: 3rem;
    font-weight: 900;
    line-height: 1;
    color: #60d394;
  }
  .my-result:not(.good) .pts-num { color: rgba(255,255,255,0.5); }

  .pts-label { font-size: 0.85rem; color: rgba(255,255,255,0.6); }
  .total-score { font-size: 0.95rem; font-weight: 700; margin-top: 0.3rem; }
  .correct-loc { font-size: 0.85rem; color: rgba(255,255,255,0.55); margin-top: 0.15rem; }
  .correct-loc.good { color: #60d394; }
  .target-year { font-size: 0.8rem; color: rgba(255,255,255,0.5); margin-top: 0.1rem; }

  .lb-section {
    background: rgba(255,255,255,0.05);
    border-radius: 14px;
    padding: 1rem 1.1rem;
  }

  .lb-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 0.6rem;
  }

  .lb-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.45rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    font-size: 0.95rem;
  }
  .lb-row:last-child { border-bottom: none; }
  .lb-row.me { color: #60d394; font-weight: 700; }
  .lb-row.winner .lb-name::after { content: ' 🏆'; }

  .lb-rank { color: rgba(255,255,255,0.35); width: 1.5rem; font-weight: 600; }
  .lb-name { flex: 1; }
  .lb-score { font-weight: 700; }

  .disconnect-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: #dc3545;
    color: white;
    text-align: center;
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
    font-weight: 600;
    z-index: 200;
  }

  .username-badge {
    position: fixed;
    top: 0.75rem;
    right: 0.75rem;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 20px;
    padding: 0.3rem 0.85rem;
    font-size: 0.82rem;
    font-weight: 700;
    color: rgba(255,255,255,0.75);
    pointer-events: none;
    z-index: 100;
  }
</style>
