<main class="wrap">
  <section class="hero">
    <p class="kicker">Party-Spiel</p>
    <h1>Halluzination</h1>
    <p class="lead">
      Entlarvt gemeinsam KI-veränderte Fotos. Wer zuerst erkennt, was am Bild nicht stimmt,
      punktet.
    </p>
  </section>

  <section class="card">
    <h2>Spielregeln</h2>
    <ol>
      <li>Das KI-veränderte Bild wird eingeblendet und kurz darauf scharf.</li>
      <li>Alle können buzzern, sobald sie eine Veränderung erkannt haben.</li>
      <li>Der Spielleiter entscheidet: richtige Antwort gibt Punkte, falsche Antwort sperrt für die Runde.</li>
      <li>Danach folgt die Quizfrage: Ort und Jahr des Fotos schätzen.</li>
      <li>Nach jeder Runde wird die Rangliste aktualisiert.</li>
      <li>Am Ende gewinnt, wer die meisten Punkte gesammelt hat.</li>
    </ol>
  </section>

  <section class="card">
    <h2>Wertung</h2>
    <ul>
      <li>Richtiger Buzzer-Hinweis: <strong>+2 Punkte</strong></li>
      <li>Richtiger Ort: <strong>+1 Punkt</strong></li>
      <li>Richtiges Jahr: <strong>+1 Punkt</strong></li>
    </ul>
  </section>

  <section class="cta">
    <p>Bereit für den nächsten Spielabend?</p>
    <a class="admin-link" href="/admin">Zum Admin-Panel</a>
  </section>
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: system-ui, sans-serif;
    background: linear-gradient(180deg, #f9fafb 0%, #edf2f7 100%);
    color: #111827;
  }

  .wrap {
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem 1rem 3rem;
    display: grid;
    gap: 1rem;
  }

  .hero {
    background: white;
    border-radius: 14px;
    padding: 1.5rem;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  }

  .kicker {
    margin: 0;
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #475569;
    font-weight: 700;
  }

  h1 {
    margin: 0.25rem 0 0;
    font-size: clamp(1.8rem, 4vw, 2.6rem);
    line-height: 1.05;
    color: #0f172a;
  }

  .lead {
    margin: 0.85rem 0 0;
    color: #334155;
    max-width: 60ch;
  }

  .card {
    background: white;
    border-radius: 14px;
    padding: 1.4rem 1.5rem;
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  }

  h2 {
    margin: 0 0 0.75rem;
    font-size: 1.2rem;
    color: #111827;
  }

  ol,
  ul {
    margin: 0;
    padding-left: 1.2rem;
    display: grid;
    gap: 0.5rem;
    color: #1f2937;
  }

  li {
    line-height: 1.45;
  }

  .cta {
    text-align: center;
    padding-top: 0.4rem;
  }

  .cta p {
    margin: 0 0 0.7rem;
    color: #334155;
    font-weight: 600;
  }

  .admin-link {
    display: inline-block;
    text-decoration: none;
    color: white;
    background: #0f172a;
    border-radius: 10px;
    padding: 0.75rem 1.2rem;
    font-weight: 700;
  }

  .admin-link:hover {
    background: #1e293b;
  }
</style>
