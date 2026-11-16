// Página do Bit a Bit: liga o motor (engine), a grelha (board), os controlos, o som e a API; mostra introdução, jogo e resultados.
import { bootPage } from "../../../services/page.js";
import { t, getLocale } from "../../../services/i18n.js";
import { toast } from "../../../components/toast.js";
import { el } from "../../../components/dom.js";
import { countTo, enter, pulse } from "../../../services/motion.js";
import { createEngine } from "../../../components/extra/bitabit/engine.js";
import { createBoard } from "../../../components/extra/bitabit/board.js";
import { createControls } from "../../../components/extra/bitabit/controls.js";
import { createAudio } from "../../../components/extra/bitabit/audio.js";
import { startGame, finishGame, loadTop, loadMine } from "../../../components/extra/bitabit/net.js";
import { DEFAULTS } from "../../../components/extra/bitabit/rng.js";

const $ = (id) => document.getElementById(id);
const fmt = (n) => new Intl.NumberFormat(getLocale()).format(n ?? 0);
const screens = { intro: $("screen-intro"), game: $("screen-game"), over: $("screen-over") };
const show = (name) => { for (const [k, n] of Object.entries(screens)) n.hidden = k !== name; };

const me = await bootPage({ access: "user", nav: false });
if (me) init();

function init() {
  const sound = createAudio();
  let game = null, engine = null, board = null, controls = null;
  let paused = false, running = false, raf = 0, last = 0, finishing = false;

  const refreshSoundBtn = () => { const b = $("b-sound"); b.setAttribute("aria-pressed", String(sound.on)); b.textContent = t(sound.on ? "bit.sound_on" : "bit.sound_off"); };
  const stats = () => {
    const s = engine.state;
    $("st-score").textContent = fmt(s.score); $("st-level").textContent = String(engine.level);
    $("st-left").textContent = String(engine.rowsLeft); $("st-streak").textContent = String(s.streak);
  };
  const activate = () => {
    const a = engine.active;
    controls.setRow(a);
    if (a) board.paintActive(a, controls.state);
  };

  function overlay(text, resume) {
    $("overlay").hidden = !text; $("overlay-text").textContent = text ?? "";
    $("b-resume").hidden = !resume;
    if (text && resume) $("b-resume").focus({ preventScroll: true });
  }
  function setPaused(p) {
    if (!running || p === paused) return;
    paused = p; last = performance.now();
    $("b-pause").textContent = t(p ? "bit.resume" : "bit.pause");
    overlay(p ? t("bit.paused") : null, p);
    p ? sound.stopMusic() : (sound.startMusic(), controls.focusInput());
  }

  async function start() {
    $("play").disabled = true;
    game = await startGame();
    $("play").disabled = false;
    $("game-note").hidden = !game.practice;
    $("game-note").textContent = t("bit.practice");
    show("game");
    board = createBoard($("board"), { capacity: { ...DEFAULTS, ...game.config }.capacity });
    board.reset();
    controls = createControls($("controls"), {
      onSubmit: (v) => { if (!paused && running) engine.submit(v); },
      onChange: (row, st) => board.paintActive(row, st),
      sfx: (n) => sound.play(n),
    });
    engine = createEngine({
      seed: game.seed, config: game.config,
      onSpawn: (row) => { board.addRow(row, row.bits); if (engine.active === row) activate(); },
      onClear: (row, gained) => {
        board.clear(row); sound.play("clear"); stats(); pulse($("st-score"));
        toast(`+${gained}`, "success");
        activate();
      },
      onWrong: (row) => { board.shake(row); sound.play("wrong"); stats(); },
      onLevel: (lv) => { sound.play("level"); toast(t("bit.level_up", { n: lv }), "info"); },
      onOver: (why) => { sound.play("over"); finish(why); },
    });
    paused = false; running = true; finishing = false; last = performance.now();
    overlay(null);
    $("b-pause").textContent = t("bit.pause");
    stats();
    sound.startMusic();
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(frame);
  }

  function frame(now) {
    if (!running) return;
    if (!paused) {
      engine.tick(Math.min(100, now - last));
      for (const r of engine.state.pending) board.place(r);
    }
    last = now;
    raf = requestAnimationFrame(frame);
  }

  async function finish(reason) {
    if (finishing) return;
    finishing = true; running = false; cancelAnimationFrame(raf); sound.stopMusic();
    const s = engine.state;
    if (reason === "top") { overlay(t("bit.game_over"), false); await new Promise((r) => setTimeout(r, 1100)); }
    overlay(null);
    const [res, top] = await Promise.all([finishGame(game, s.answers, s.score), loadTop()]);
    results(res, top, s.score);
  }

  function results(res, top, score) {
    show("over");
    $("res-title").textContent = t("bit.over_title");
    const practice = game.practice || !res;
    $("res-note").textContent = practice ? t(game.practice ? "bit.practice" : "bit.save_failed") : "";
    $("res-note").hidden = !practice;
    const shown = res?.score ?? score;
    const today = res ? Math.max(0, 50 - (res.today_remaining ?? 50)) : null;
    $("res-points").textContent = res ? `+${res.points_awarded ?? 0}` : "—";
    $("res-today").textContent = today == null ? "—" : `${today}/50`;
    $("res-best").textContent = res?.best != null ? fmt(res.best) : "—";
    countTo($("res-score"), shown);
    const list = $("res-top");
    list.replaceChildren(...(top ?? []).map((e) => el("li", { class: `bit-top__row${e.me ? " is-me" : ""}` }, el("b", {}, `#${e.rank}`), el("span", { class: "truncate" }, e.name), el("span", {}, fmt(e.score)))));
    $("res-top-empty").hidden = !!(top && top.length);
    enter(screens.over.querySelectorAll(".panel-pixel"), { stagger: 0.1 });
    $("again").focus({ preventScroll: true });
  }

  $("play").addEventListener("click", start);
  $("again").addEventListener("click", start);
  $("b-pause").addEventListener("click", () => setPaused(!paused));
  $("b-resume").addEventListener("click", () => setPaused(false));
  $("b-sound").addEventListener("click", () => { sound.set(!sound.on); refreshSoundBtn(); if (sound.on) { sound.play("level"); if (running && !paused) sound.startMusic(); } });
  $("b-end").addEventListener("click", () => { if (running) finish("end"); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) setPaused(true); });
  document.addEventListener("localechange", () => { refreshSoundBtn(); if (engine) { stats(); activate(); } $("b-pause").textContent = t(paused ? "bit.resume" : "bit.pause"); });
  $("board").addEventListener("click", (e) => { const c = running && !paused && board.cellAt(e.target); if (c) controls.toggleAt(c.index); });
  document.addEventListener("keydown", (e) => {
    if (!running) return;
    if (e.key === "Escape" || e.key === "p" || e.key === "P") { if (!e.target.closest?.("input")) { setPaused(!paused); e.preventDefault(); } return; }
    if (paused) return;
    if (controls.key(e)) e.preventDefault();
  });
  refreshSoundBtn();
  let mine = null;
  const introNote = () => { $("intro-note").textContent = t("bit.intro_note") + (mine ? ` ${t("bit.today", { x: mine.today_points ?? 0, max: mine.daily_cap ?? 50, best: fmt(mine.best_score ?? 0) })}` : ""); };
  introNote();
  loadMine().then((m) => { mine = m; introNote(); });
  document.addEventListener("localechange", introNote);
}
